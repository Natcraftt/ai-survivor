"""Le monde : l'état de la partie et les règles pour passer d'un tour au suivant.

Aucune dépendance à une fenêtre : le monde ne sait pas comment il est affiché.
Coordonnées (x, y) : x vers la droite, y vers le bas. La case (x, y) se lit walls[y][x].

Ordre d'un tour (toujours le même) :
  1. le joueur agit ;
  2. chaque zombie agit, dans l'ordre de la liste (attaque s'il est adjacent, sinon avance) ;
  3. un zombie peut apparaître ;
  4. le compteur de tours avance.
"""

import random
from dataclasses import asdict, dataclass

from .actions import MOVES, Action


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


class World:
    def __init__(self, config=None, seed=None):
        self.config = config or WorldConfig()
        self.rng = random.Random(seed)  # un générateur par monde, jamais le global
        self.reset()

    @property
    def size(self):
        return self.config.size

    def reset(self, seed=None):
        """Remet le monde à son état de départ. Avec `seed`, le hasard repart de cette graine."""
        if seed is not None:
            self.rng = random.Random(seed)
        c = self.config
        n = c.size
        self.nb_tours = 0
        self.hp = c.max_hp
        self.walls = [
            [x in (0, n - 1) or y in (0, n - 1) for x in range(n)] for y in range(n)
        ]
        self.player = (n // 2, n // 2)
        self.zombies = []
        candidates = self._spawn_candidates()
        count = min(c.n_zombies, len(candidates))
        for x, y in self.rng.sample(candidates, count):
            self.zombies.append(Zombie(x, y, c.zombie_hp))

    def in_grid(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def is_free(self, x, y):
        return self.in_grid(x, y) and not self.walls[y][x]

    def zombie_at(self, x, y):
        for z in self.zombies:
            if z.x == x and z.y == y:
                return z
        return None

    def _spawn_candidates(self):
        n = self.size
        return [
            (x, y)
            for y in range(n)
            for x in range(n)
            if self.is_free(x, y)
            and self.zombie_at(x, y) is None
            and manhattan((x, y), self.player) >= self.config.min_spawn_distance
        ]

    @property
    def dead(self):
        return self.hp <= 0

    def is_done(self):
        return self.dead or self.nb_tours >= self.config.max_steps

    def add_wall(self, x, y):
        if not self.in_grid(x, y):
            raise ValueError(f"({x}, {y}) est hors de la grille")
        if (x, y) == self.player or self.zombie_at(x, y) is not None:
            raise ValueError("On ne peut pas poser un mur sur le joueur ni sur un zombie")
        self.walls[y][x] = True

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
        return {
            "nb_tours": self.nb_tours,
            "config": asdict(self.config),
            "walls": [row[:] for row in self.walls],
            "player": list(self.player),
            "hp": self.hp,
            "zombies": [{"x": z.x, "y": z.y, "hp": z.hp} for z in self.zombies],
        }

    def from_dict(self, data):
        self.config = WorldConfig(**data["config"])
        self.nb_tours = data["nb_tours"]
        self.walls = [row[:] for row in data["walls"]]
        self.player = tuple(data["player"])
        self.hp = data["hp"]
        self.zombies = [Zombie(z["x"], z["y"], z["hp"]) for z in data["zombies"]]