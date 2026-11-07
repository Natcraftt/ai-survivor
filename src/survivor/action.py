"""Les actions que l'agent peut choisir."""

from enum import IntEnum


class Action(IntEnum):
    HAUT = 0
    DROITE = 1
    BAS = 2
    GAUCHE = 3
    ATTENDRE = 4


# Décalage (dx, dy) de chaque déplacement. x vers la droite, y vers le bas.
MOVES = {
    Action.HAUT: (0, -1),
    Action.DROITE: (1, 0),
    Action.BAS: (0, 1),
    Action.GAUCHE: (-1, 0),
}