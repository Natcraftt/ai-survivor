"""Ce que l'agent perçoit : un vecteur de nombres entre -1 et 1.

NOUVEAU (ticket 1.6) : version minimale, juste assez pour brancher un apprentissage.
Elle sera enrichie plus tard (jalons suivants).

La perception est « égocentrique » : tout est mesuré par rapport au joueur, jamais en
coordonnées absolues. L'agent apprend ainsi des principes (« un zombie à ma droite, un mur
derrière moi ») et pas des positions (« un zombie en (9, 4) »). Un réseau de neurones ne sait
manipuler que des nombres, d'où ce vecteur.
"""

import numpy as np

WINDOW = 2  # on voit les cases à 2 pas autour du joueur : une fenêtre de 5 x 5
SIDE = 2 * WINDOW + 1

# Disposition du vecteur (chaque constante = position de départ d'un bloc de valeurs)
IDX_HP = 0  # PV / PV max, entre 0 et 1
IDX_AMMO = 1  # balles / balles d'une arme neuve, entre 0 et 1
IDX_MEDKITS = 2  # medkits en poche / 3, entre 0 et 1
IDX_WALLS = 3  # 25 valeurs : 1.0 = mur ou hors de la carte, 0.0 = libre
IDX_ZOMBIES = IDX_WALLS + SIDE * SIDE  # 25 valeurs : 1.0 = zombie sur la case
IDX_NEAREST = IDX_ZOMBIES + SIDE * SIDE  # 4 valeurs : présent ?, dx, dy, distance
IDX_COUNT = IDX_NEAREST + 4  # nombre de zombies / maximum
IDX_WEAPON = IDX_COUNT + 1  # 3 valeurs : présente sur la carte ?, dx, dy
IDX_MEDKIT = IDX_WEAPON + 3  # 3 valeurs : présent sur la carte ?, dx, dy
OBSERVATION_SIZE = IDX_MEDKIT + 3


def window_index(dx, dy):
    """Position, dans un bloc de fenêtre, de la case décalée de (dx, dy) par rapport au joueur."""
    return (dy + WINDOW) * SIDE + (dx + WINDOW)


def _relative(world, position):
    """(présent, dx, dy) d'un objet par rapport au joueur. Tout à 0 si l'objet n'existe pas."""
    if position is None:
        return [0.0, 0.0, 0.0]
    n = world.config.size
    return [1.0, (position[0] - world.player[0]) / n, (position[1] - world.player[1]) / n]


def observe(world):
    """Transforme l'état du monde en vecteur de nombres (float32, valeurs entre -1 et 1)."""
    c = world.config
    px, py = world.player

    # Fenêtre locale : deux « calques » de 5 x 5, un pour les murs, un pour les zombies.
    murs, zombies = [], []
    for dy in range(-WINDOW, WINDOW + 1):
        for dx in range(-WINDOW, WINDOW + 1):
            x, y = px + dx, py + dy
            murs.append(0.0 if world.is_free(x, y) else 1.0)  # hors carte = mur
            zombies.append(1.0 if world.zombie_at(x, y) is not None else 0.0)

    z, distance = world.nearest_zombie()
    if z is None:
        plus_proche = [0.0, 0.0, 0.0, 0.0]
    else:
        plus_proche = [1.0, (z.x - px) / c.size, (z.y - py) / c.size, distance / (2 * c.size)]

    features = [
        world.hp / c.max_hp,
        min(1.0, world.ammo / max(1, c.weapon_ammo)),
        min(1.0, world.medkits / 3),
        *murs,
        *zombies,
        *plus_proche,
        min(1.0, len(world.zombies) / c.max_zombies),
        *_relative(world, world.weapon_pos),
        *_relative(world, world.medkit_pos),
    ]
    return np.asarray(features, dtype=np.float32)