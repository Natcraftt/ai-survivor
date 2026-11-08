"""Tests du masque d'actions (ticket 1.6) : à chaque tour, quelles actions ont un effet ?"""

import random

from survivor.actions import MOVES, N_ACTIONS, Action
from survivor.world import World, WorldConfig, Zombie


def monde(**reglages):
    """Arène vide, sans zombie ni objet, joueur au centre (6, 6)."""
    base = {
        "n_zombies": 0, "spawn_prob": 0.0, "place_items": False, "zombie_move_prob": 0.0,
        "wall_density": 0.0, "random_start": False,
    }
    base.update(reglages)
    return World(WorldConfig(**base), seed=0)


def test_le_masque_a_une_valeur_par_action():
    w = monde()
    assert len(w.action_mask()) == N_ACTIONS == 7


def test_dans_une_arene_vide_seuls_les_deplacements_et_attendre_sont_possibles():
    mask = monde().action_mask()
    assert mask[Action.HAUT] and mask[Action.DROITE] and mask[Action.BAS] and mask[Action.GAUCHE]
    assert mask[Action.ATTENDRE]
    assert not mask[Action.ATTAQUER]  # personne à frapper
    assert not mask[Action.SOIGNER]  # ni medkit ni blessure


def test_attendre_est_toujours_possible():
    w = monde()
    w.hp = 1
    w.zombies.append(Zombie(7, 6))
    assert w.action_mask()[Action.ATTENDRE]


def test_les_murs_bloquent_les_deplacements():
    w = monde()
    w.player = (1, 1)  # dans l'angle haut-gauche
    mask = w.action_mask()
    assert not mask[Action.HAUT] and not mask[Action.GAUCHE]
    assert mask[Action.DROITE] and mask[Action.BAS]


def test_un_mur_pose_au_milieu_bloque_la_direction_correspondante():
    w = monde()
    w.add_wall(7, 6)
    assert not w.action_mask()[Action.DROITE]


def test_un_zombie_adjacent_bloque_le_deplacement_vers_lui_mais_permet_de_frapper():
    w = monde()
    w.zombies.append(Zombie(7, 6))
    mask = w.action_mask()
    assert not mask[Action.DROITE]
    assert mask[Action.ATTAQUER]  # coup de poing


def test_attaquer_sans_balle_est_impossible_hors_contact():
    w = monde()
    w.zombies.append(Zombie(8, 6))  # distance 2, pas de balles
    assert not w.action_mask()[Action.ATTAQUER]


def test_attaquer_avec_balles_depend_de_la_portee():
    w = monde()
    w.ammo = 4
    w.zombies.append(Zombie(9, 6))  # distance 3 = portée maximale
    assert w.action_mask()[Action.ATTAQUER]
    w.zombies[0].x = 10  # distance 4 : trop loin
    assert not w.action_mask()[Action.ATTAQUER]


def test_se_soigner_demande_un_medkit_et_d_etre_blesse():
    w = monde()
    assert not w.action_mask()[Action.SOIGNER]  # ni l'un ni l'autre
    w.medkits = 1
    assert not w.action_mask()[Action.SOIGNER]  # medkit mais pleine santé
    w.hp = 3
    assert w.action_mask()[Action.SOIGNER]  # medkit ET blessé
    w.medkits = 0
    assert not w.action_mask()[Action.SOIGNER]  # blessé mais sans medkit


def test_les_valeurs_du_masque_sont_de_vrais_booleens():
    assert all(isinstance(v, bool) for v in monde().action_mask())


def test_le_masque_ne_ment_jamais():
    # Le test le plus important : pour CHAQUE action de CHAQUE situation, on la joue sur une
    # copie exacte du monde et on vérifie que le masque disait vrai.
    # (La copie passe par to_dict/from_dict, qui conserve aussi le hasard.)
    for seed in range(20):
        w = World(WorldConfig(max_hp=1000), seed=seed)
        hasard = random.Random(seed)
        for _ in range(40):
            if w.is_done():
                break
            mask = w.action_mask()
            for action in Action:
                copie = World()
                copie.from_dict(w.to_dict())
                avant = (copie.ammo, copie.medkits, copie.hp, [z.hp for z in copie.zombies])
                copie.step(action)

                if action in MOVES:
                    dx, dy = MOVES[action]
                    attendu = (w.player[0] + dx, w.player[1] + dy) if mask[action] else w.player
                    assert copie.player == attendu, (seed, action)
                elif action == Action.ATTAQUER:
                    hp_zombies_avant = avant[3]
                    hp_zombies_apres = [z.hp for z in copie.zombies[: len(hp_zombies_avant)]]
                    a_change = (
                        copie.ammo != avant[0]
                        or len(copie.zombies) < len(hp_zombies_avant)
                        or hp_zombies_apres != hp_zombies_avant
                    )
                    assert a_change == mask[action], (seed, action)
                elif action == Action.SOIGNER:
                    assert (copie.medkits == avant[1] - 1) == mask[action], (seed, action)

            valides = [a for a in Action if mask[a]]
            w.step(hasard.choice(valides))