"""Le monde : l'état de la partie et les règles pour passer d'un tour au suivant.
"""

from actions.py import MOVES, Action


class World:
    NB_MAX_TOUR = 150

    def __init__(self, size=12):
        self.size = size
        self.reset()

    def reset(self):
        """Remet le monde à son état de départ."""
        self.nb_tours = 0
        self.walls = [
            [x in (0, self.size - 1) or y in (0, self.size - 1) for x in range(self.size)]
            for y in range(self.size)
        ]
        self.player = (self.size // 2, self.size // 2)

    def in_grid(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def is_free(self, x, y):
        """Vrai si la case est dans la grille et sans mur. Refuse les coordonnées négatives."""
        return self.in_grid(x, y) and not self.walls[y][x]

    def add_wall(self, x, y):
        if not self.in_grid(x, y):
            raise ValueError(f"({x}, {y}) est hors de la grille")
        if (x, y) == self.player:
            raise ValueError("On ne peut pas poser un mur sur le joueur")
        self.walls[y][x] = True

    def step(self, action):
        """Fait avancer le monde d'un tour. Déplace le joueur si la case visée est libre."""
        if self.is_done():
            raise RuntimeError("La partie est finie : appelle reset() avant de rejouer.")
        action = Action(int(action))
        if action in MOVES:
            dx, dy = MOVES[action]
            x, y = self.player[0] + dx, self.player[1] + dy
            if self.is_free(x, y):
                self.player = (x, y)
        self.nb_tours += 1

    def is_done(self):
        return self.nb_tours >= self.NB_MAX_TOUR

    def to_dict(self):
        return {
            "nb_tours": self.nb_tours,
            "size": self.size,
            "walls": [row[:] for row in self.walls],  # copie : l'export est indépendant du monde
            "player": list(self.player),
        }

    def from_dict(self, data):
        self.nb_tours = data["nb_tours"]
        self.size = data["size"]
        self.walls = [row[:] for row in data["walls"]]  # copie : le monde est indépendant des données
        self.player = tuple(data["player"])