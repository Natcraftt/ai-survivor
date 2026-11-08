"""Récompense : le signal qui dit à l'IA si ce qu'elle vient de faire est bien ou mal.

NOUVEAU (ticket 1.6) : récompense minimale, juste pour pouvoir brancher un apprentissage.
Elle sera remplacée plus tard par une récompense issue de la variation des besoins.
"""

SURVIE = 1.0  # gagné à chaque tour où le joueu r est encore en vie
MORT = -10.0  # perdu au tour de la mort : mourir tôt est très mauvais


def compute_reward(world):
    return MORT if world.dead else SURVIE