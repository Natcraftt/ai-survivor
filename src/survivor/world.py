"""Le monde : l'état de la partie et les règles pour passer d'un tour au suivant.

Aucune dépendance à une fenêtre : le monde ne sait pas comment il est affiché.
Coordonnées (x, y) : x vers la droite, y vers le bas. La case (x, y) se lit walls[y][x].

Le hasard : chaque partie a sa graine (self.seed). Même graine = même carte, mêmes
zombies, mêmes objets, et même suite d'événements aléatoires pendant la partie.

Ordre d'un tour (toujours le même) :
  1. le joueur agit (se déplace, attaque ou se soigne) ;
  2. chaque zombie agit, dans l'ordre de la liste (attaque s'il est adjacent, sinon avance) ;
  3. un zombie peut apparaître ;
  4. le compteur de tours avance.
Conséquence : un zombie tué à l'étape 1 n'attaque pas à l'étape 2.
"""

import random
from collections import deque
from dataclasses import asdict, dataclass

from .actions import MOVES, N_ACTIONS, Action


@dataclass
class WorldConfig:
    size: int = 12
    max_steps: int = 150
    max_hp: int = 5
    n_zombies: int = 2  # zombies au départ
    max_zombies: int = 5  # plafond (départ + apparitions)
    spawn_prob: float = 0.01  # probabilité qu'un zombie apparaisse à chaque tour
    zombie_move_prob: float = 0.8  # probabilité qu'un zombie avance à chaque tour
    zombie_hp: int = 2
    zombie_damage: int = 1
    min_spawn_distance: int = 5  # distance minimale (Manhattan) au joueur

    # --- réglages de l'arme et du medkit ---
    place_items: bool = True  # poser une arme et un medkit à la création (False pour les tests)
    weapon_ammo: int = 4  # balles reçues en ramassant l'arme
    weapon_range: int = 3  # portée d'un tir (distance de Manhattan, murs ignorés)
    weapon_damage: int = 2  # dégâts d'un tir : un zombie a 2 PV, un tir suffit
    punch_damage: int = 1  # dégâts d'un coup de poing (portée 1 seulement)
    medkit_heal: int = 3  # PV rendus par un medkit

    # --- variété des cartes ---
    # Pour que l'IA apprenne des PRINCIPES (« je suis acculé contre un mur ») et pas des
    # POSITIONS (« en (4, 7) il y a un mur »), chaque partie doit avoir une carte différente.
    wall_density: float = 0.12  # part des cases intérieures qui sont des murs (0 = arène vide)
    random_start: bool = True  # joueur placé au hasard (False = toujours au centre)


@dataclass
class Zombie:
    x: int
    y: int
    hp: int = 2


def manhattan(a, b):
    """Nombre de pas pour aller de a à b sans diagonale, murs ignorés."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def sign(n):
    return (n > 0) - (n < 0)


MAX_MAP_ATTEMPTS = 100  # essais pour obtenir une carte valide avant de renoncer aux murs


def _tout_est_connecte(walls, libres, n):
    """Vrai si, depuis la première case libre, on peut atteindre TOUTES les autres.

    On explore de proche en proche (parcours en largeur). Sans cette garantie, une carte
    aléatoire pourrait enfermer le joueur, ou une arme, dans une poche entourée de murs.
    """
    depart = libres[0]
    vues = {depart}
    a_visiter = deque([depart])
    while a_visiter:
        x, y = a_visiter.popleft()
        for dx, dy in MOVES.values():
            nx, ny = x + dx, y + dy
            if 0 <= nx < n and 0 <= ny < n and not walls[ny][nx] and (nx, ny) not in vues:
                vues.add((nx, ny))
                a_visiter.append((nx, ny))
    return len(vues) == len(libres)


def _rng_vers_liste(rng):
    """État complet d'un générateur aléatoire, sous une forme qui s'écrit en JSON."""
    version, interne, gauss = rng.getstate()
    return [version, list(interne), gauss]


def _rng_depuis_liste(donnees):
    """Recrée un générateur exactement dans l'état exporté par _rng_vers_liste."""
    version, interne, gauss = donnees
    rng = random.Random()
    rng.setstate((version, tuple(interne), gauss))
    return rng


class World:
    def __init__(self, config=None, seed=None):
        self.config = config or WorldConfig()
        # DEUX générateurs, jamais le générateur global :
        #  - _seeder fabrique les graines des parties successives (reset() sans argument) ;
        #  - self.rng (créé dans reset) fait le hasard à l'intérieur d'UNE partie.
        # La première partie utilise exactement la graine donnée : World(seed=5).seed == 5.
        self._seeder = random.Random(seed)
        self.reset(seed)

    @property
    def size(self):
        return self.config.size

    def reset(self, seed=None):
        """Remet le monde à son état de départ (une nouvelle partie).

        Chaque partie a sa graine, rangée dans self.seed.
          - reset(seed=42) : la partie 42, toujours la même ;
          - reset()        : une nouvelle partie dont la graine est tirée de la suite de graines
                             du monde (cette suite est elle-même reproductible).
        Pour rejouer une partie qui a posé problème, il suffit de relever son self.seed.
        """
        if seed is None:
            seed = self._seeder.getrandbits(32)
        self.seed = seed
        self.rng = random.Random(seed)
        c = self.config
        n = c.size
        self.nb_tours = 0
        self.hp = c.max_hp
        self.walls, self.player = self._generate_map()

        # --- inventaire du joueur et objets posés sur la carte ---
        self.has_weapon = False  # a-t-on déjà ramassé l'arme ? (reste vrai même sans balles)
        self.ammo = 0  # balles restantes
        self.medkits = 0  # medkits en poche
        self.weapon_pos = None  # position de l'arme sur la carte, None si absente ou ramassée
        self.medkit_pos = None  # idem pour le medkit
        if c.place_items:
            # Cases libres où poser un objet : toutes sauf celle du joueur.
            libres = [
                (x, y)
                for y in range(n)
                for x in range(n)
                if self.is_free(x, y) and (x, y) != self.player
            ]
            # sample() tire des cases DISTINCTES : l'arme et le medkit ne sont jamais ensemble.
            # min(2, ...) évite une erreur sur une carte minuscule qui n'aurait pas assez de cases.
            tirees = self.rng.sample(libres, min(2, len(libres)))
            if len(tirees) > 0:
                self.weapon_pos = tirees[0]
            if len(tirees) > 1:
                self.medkit_pos = tirees[1]

        # Les zombies sont placés APRÈS les objets : _spawn_candidates évite les cases d'objets.
        self.zombies = []
        candidates = self._spawn_candidates()
        count = min(c.n_zombies, len(candidates))
        for x, y in self.rng.sample(candidates, count):
            self.zombies.append(Zombie(x, y, c.zombie_hp))

    # --- génération de la carte ---
    def _generate_map(self):
        """Retourne (walls, position du joueur) : bordure + murs intérieurs au hasard.

        On tire des murs, et on RECOMMENCE tant que la carte n'est pas connectée. Si aucun des
        MAX_MAP_ATTEMPTS essais ne convient (densité absurde, carte minuscule), on se rabat sur
        une arène vide plutôt que de planter.
        """
        c = self.config
        n = c.size
        centre = (n // 2, n // 2)

        for _ in range(MAX_MAP_ATTEMPTS):
            # `or` s'arrête dès qu'il trouve True : les cases du bord sont murées sans tirage,
            # les autres tirent un nombre aléatoire contre la densité.
            walls = [
                [
                    x in (0, n - 1) or y in (0, n - 1) or self.rng.random() < c.wall_density
                    for x in range(n)
                ]
                for y in range(n)
            ]
            if not c.random_start:
                walls[centre[1]][centre[0]] = False  # le départ au centre doit être libre
            libres = [(x, y) for y in range(n) for x in range(n) if not walls[y][x]]
            if libres and _tout_est_connecte(walls, libres, n):
                return walls, self._choisir_depart(libres, centre)

        walls = [[x in (0, n - 1) or y in (0, n - 1) for x in range(n)] for y in range(n)]
        libres = [(x, y) for y in range(n) for x in range(n) if not walls[y][x]]
        return walls, self._choisir_depart(libres, centre)

    def _choisir_depart(self, libres, centre):
        return self.rng.choice(libres) if self.config.random_start else centre

    # ------------------------------------------------------------------ requêtes
    def in_grid(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def is_free(self, x, y):
        """Vrai si la case est dans la grille et sans mur. Refuse les coordonnées négatives."""
        return self.in_grid(x, y) and not self.walls[y][x]

    def zombie_at(self, x, y):
        for z in self.zombies:
            if z.x == x and z.y == y:
                return z
        return None

    def nearest_zombie(self):
        """Retourne (zombie, distance) du plus proche, ou (None, None).

        Sert à l'attaque : on frappe toujours le zombie le plus proche.
        En cas d'égalité, min() garde le premier de la liste.
        """
        if not self.zombies:
            return None, None
        z = min(self.zombies, key=lambda z: manhattan((z.x, z.y), self.player))
        return z, manhattan((z.x, z.y), self.player)

    def action_mask(self):
        """NOUVEAU (ticket 1.6). Liste de booléens, un par action : True = l'action a un effet.

        Pourquoi : sans masque, l'IA perd beaucoup de temps à essayer des actions impossibles
        (marcher dans un mur, se soigner sans medkit). Avec le masque, on lui dit à chaque tour
        lesquelles ont un effet, et elle choisit uniquement parmi celles-là.

        - déplacement : possible si la case visée est libre (ni mur, ni zombie) ;
        - ATTENDRE    : toujours possible, donc au moins une action est toujours valide ;
        - ATTAQUER    : possible s'il y a un zombie à portée de tir (avec des balles) ou adjacent ;
        - SOIGNER     : possible si on a un medkit ET qu'on est blessé.
        Ces conditions sont les mêmes que celles de step() : le masque ne ment jamais.
        """
        mask = [False] * N_ACTIONS
        for action, (dx, dy) in MOVES.items():
            x, y = self.player[0] + dx, self.player[1] + dy
            mask[action] = self.is_free(x, y) and self.zombie_at(x, y) is None
        mask[Action.ATTENDRE] = True
        z, distance = self.nearest_zombie()
        if z is not None:
            en_portee = self.ammo > 0 and distance <= self.config.weapon_range
            mask[Action.ATTAQUER] = en_portee or distance <= 1
        mask[Action.SOIGNER] = self.medkits > 0 and self.hp < self.config.max_hp
        return mask

    def _spawn_candidates(self):
        """Cases où un zombie peut apparaître : libres, sans zombie, sans objet, loin du joueur."""
        n = self.size
        return [
            (x, y)
            for y in range(n)
            for x in range(n)
            if self.is_free(x, y)
            and self.zombie_at(x, y) is None
            and (x, y) not in (self.weapon_pos, self.medkit_pos)
            and manhattan((x, y), self.player) >= self.config.min_spawn_distance
        ]

    @property
    def dead(self):
        return self.hp <= 0

    def is_done(self):
        return self.dead or self.nb_tours >= self.config.max_steps

    # ------------------------------------------------------------------ construction de scénarios
    def add_wall(self, x, y):
        if not self.in_grid(x, y):
            raise ValueError(f"({x}, {y}) est hors de la grille")
        if (x, y) == self.player or self.zombie_at(x, y) is not None:
            raise ValueError("On ne peut pas poser un mur sur le joueur ni sur un zombie")
        # un mur sur un objet le rendrait introuvable.
        if (x, y) in (self.weapon_pos, self.medkit_pos):
            raise ValueError("On ne peut pas poser un mur sur un objet")
        self.walls[y][x] = True

    # ------------------------------------------------------------------ dynamique
    def step(self, action):
        """Joue un tour complet (voir l'ordre en haut du fichier)."""
        if self.is_done():
            raise RuntimeError("La partie est finie : appelle reset() avant de rejouer.")
        action = Action(int(action))  # lève ValueError si le numéro n'existe pas

        # 1. le joueur agit
        if action in MOVES:
            dx, dy = MOVES[action]
            x, y = self.player[0] + dx, self.player[1] + dy
            if self.is_free(x, y) and self.zombie_at(x, y) is None:
                self.player = (x, y)
                self._pickup()  # on ramasse ce qui se trouve sur la case
        # deux nouvelles actions
        elif action == Action.ATTAQUER:
            self._attack()
        elif action == Action.SOIGNER:
            self._heal()

        # 2. les zombies agissent
        c = self.config
        for z in self.zombies:
            if manhattan((z.x, z.y), self.player) == 1:
                self.hp = max(0, self.hp - c.zombie_damage)
            elif self.rng.random() < c.zombie_move_prob:
                self._move_zombie(z)

        # 3. apparition éventuelle
        if len(self.zombies) < c.max_zombies and self.rng.random() < c.spawn_prob:
            candidates = self._spawn_candidates()
            if candidates:
                x, y = self.rng.choice(candidates)
                self.zombies.append(Zombie(x, y, c.zombie_hp))

        # 4. le temps passe
        self.nb_tours += 1

    # --- ramassage, attaque, soin ---
    def _pickup(self):
        """Ramasse automatiquement l'objet de la case où le joueur vient d'arriver."""
        c = self.config
        if self.weapon_pos == self.player:
            self.weapon_pos = None  # l'objet disparaît de la carte : on ne peut le ramasser qu'une fois
            self.has_weapon = True
            self.ammo += c.weapon_ammo
        if self.medkit_pos == self.player:
            self.medkit_pos = None
            self.medkits += 1

    def _attack(self):
        """Frappe le zombie le plus proche.

        - avec des balles et un zombie à portée (<= weapon_range) : un tir, qui coûte 1 balle ;
        - sinon, avec un zombie adjacent : un coup de poing ;
        - sinon : l'attaque rate et ne coûte rien (on ne gaspille pas de balle dans le vide).
        """
        c = self.config
        z, distance = self.nearest_zombie()
        if z is None:
            return
        if self.ammo > 0 and distance <= c.weapon_range:
            self.ammo -= 1
            self._hit(z, c.weapon_damage)
        elif distance <= 1:
            self._hit(z, c.punch_damage)

    def _hit(self, z, damage):
        """Inflige des dégâts à un zombie ; il disparaît à 0 PV."""
        z.hp -= damage
        if z.hp <= 0:
            self.zombies.remove(z)

    def _heal(self):
        """Utilise un medkit si on en a un ET si on est blessé (sinon on ne le gaspille pas)."""
        c = self.config
        if self.medkits > 0 and self.hp < c.max_hp:
            self.medkits -= 1
            self.hp = min(c.max_hp, self.hp + c.medkit_heal)  # min() : jamais plus que le maximum

    def _move_zombie(self, z):
        """Poursuite gloutonne : avance sur l'axe le plus éloigné, sinon sur l'autre, sinon reste."""
        px, py = self.player
        dx, dy = sign(px - z.x), sign(py - z.y)
        if abs(px - z.x) >= abs(py - z.y):
            essais = [(dx, 0), (0, dy)]
        else:
            essais = [(0, dy), (dx, 0)]
        for ex, ey in essais:
            if ex == 0 and ey == 0:
                continue
            x, y = z.x + ex, z.y + ey
            if self.is_free(x, y) and (x, y) != self.player and self.zombie_at(x, y) is None:
                z.x, z.y = x, y
                return

    # ------------------------------------------------------------------ sauvegarde
    def to_dict(self):
        """Export copié : modifier le monde ensuite ne change pas le dictionnaire.

        Le résultat ne contient que des nombres, listes, booléens et None : il s'écrit tel quel en JSON.
        """
        return {
            "nb_tours": self.nb_tours,
            "config": asdict(self.config),
            "walls": [row[:] for row in self.walls],
            "player": list(self.player),
            "hp": self.hp,
            "zombies": [{"x": z.x, "y": z.y, "hp": z.hp} for z in self.zombies],
            "has_weapon": self.has_weapon,
            "ammo": self.ammo,
            "medkits": self.medkits,
            # Un tuple n'existe pas en JSON : on exporte une liste, ou None si l'objet n'est plus là.
            "weapon_pos": list(self.weapon_pos) if self.weapon_pos else None,
            "medkit_pos": list(self.medkit_pos) if self.medkit_pos else None,
            # --- le hasard fait partie de l'état ---
            # Sans ça, un monde reconstruit aurait la même carte mais PAS la même suite
            # d'événements aléatoires (mouvements et apparitions de zombies).
            "seed": self.seed,
            "rng_state": _rng_vers_liste(self.rng),  # le hasard de la partie en cours
            "seeder_state": _rng_vers_liste(self._seeder),  # la suite des parties suivantes
        }

    def from_dict(self, data):
        """Reconstruction copiée : modifier `data` ensuite ne change pas le monde."""
        self.config = WorldConfig(**data["config"])
        self.nb_tours = data["nb_tours"]
        self.walls = [row[:] for row in data["walls"]]
        self.player = tuple(data["player"])
        self.hp = data["hp"]
        self.zombies = [Zombie(z["x"], z["y"], z["hp"]) for z in data["zombies"]]
        self.has_weapon = data["has_weapon"]
        self.ammo = data["ammo"]
        self.medkits = data["medkits"]
        self.weapon_pos = tuple(data["weapon_pos"]) if data["weapon_pos"] else None
        self.medkit_pos = tuple(data["medkit_pos"]) if data["medkit_pos"] else None
        self.seed = data["seed"]
        self.rng = _rng_depuis_liste(data["rng_state"])
        self._seeder = _rng_depuis_liste(data["seeder_state"])