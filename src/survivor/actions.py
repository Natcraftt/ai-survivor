"""Les actions que l'agent peut choisir."""

from enum import IntEnum


class Action(IntEnum):
    HAUT = 0
    DROITE = 1
    BAS = 2
    GAUCHE = 3
    ATTENDRE = 4
    ATTAQUER = 5  # frappe le zombie le plus proche (tir si on a des balles, sinon coup de poing)
    SOIGNER = 6  # utilise un medkit


MOVES = {
    Action.HAUT: (0, -1),
    Action.DROITE: (1, 0),
    Action.BAS: (0, 1),
    Action.GAUCHE: (-1, 0),
}


N_ACTIONS = len(Action)