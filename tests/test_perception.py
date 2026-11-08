"""Tests de l'observation (ticket 1.6) : ce que l'agent perçoit, sous forme de nombres."""

import random

import numpy as np

from survivor.actions import Action
from survivor.perception import (
    IDX_AMMO, IDX_COUNT, IDX_HP, IDX_MEDKIT, IDX_MEDKITS, IDX_NEAREST, IDX_WALLS, IDX_WEAPON,
    IDX_ZOMBIES, OBSERVATION_SIZE, SIDE, WINDOW, observe, window_index,
)
from survivor.world import World, WorldConfig, Zombie


def monde(**reglages):
    """Arène vide, sans zombie ni objet, joueur au centre (6, 6)."""
    base = {
        "n_zombies": 0, "spawn_prob": 0.0, "place_items": False, "zombie_move_prob": 0.0,
        "wall_density": 0.0, "random_start": False,
    }
    base.update(reglages)
    return World(WorldConfig(**base), seed=0)


def test_l_observation_a_la_bonne_forme_et_le_bon_type():
    obs = observe(World(seed=0))
    assert obs.shape == (OBSERVATION_SIZE,) == (64,)
    assert obs.dtype == np.float32


def test_les_valeurs_restent_entre_moins_un_et_un_pendant_des_parties_entieres():
    for seed in range(30):
        w = World(seed=seed)
        hasard = random.Random(seed)
        while not w.is_done():
            obs = observe(w)
            assert obs.min() >= -1.0 and obs.max() <= 1.0, seed
            assert not np.isnan(obs).any(), seed
            w.step(hasard.choice([a for a in Action if w.action_mask()[a]]))


def test_la_meme_situation_donne_la_meme_observation():
    assert np.array_equal(observe(World(seed=4)), observe(World(seed=4)))


# ------------------------------------------------------------------ l'état du joueur
def test_les_pv_sont_normalises():
    w = monde()
    assert observe(w)[IDX_HP] == 1.0
    w.hp = 2
    assert np.isclose(observe(w)[IDX_HP], 0.4)


def test_les_balles_et_les_medkits_sont_normalises():
    w = monde()
    obs = observe(w)
    assert obs[IDX_AMMO] == 0.0 and obs[IDX_MEDKITS] == 0.0
    w.ammo = 2
    w.medkits = 1
    obs = observe(w)
    assert np.isclose(obs[IDX_AMMO], 0.5)  # 2 balles sur 4
    assert np.isclose(obs[IDX_MEDKITS], 1 / 3)


# ------------------------------------------------------------------ la fenêtre autour du joueur
def test_la_case_du_joueur_est_libre_et_sans_zombie():
    obs = observe(monde())
    centre = window_index(0, 0)
    assert obs[IDX_WALLS + centre] == 0.0
    assert obs[IDX_ZOMBIES + centre] == 0.0


def test_la_fenetre_voit_les_murs_et_le_hors_carte():
    w = monde()
    w.player = (1, 1)  # angle haut-gauche : le mur de bordure est tout près
    obs = observe(w)
    assert obs[IDX_WALLS + window_index(-1, 0)] == 1.0  # (0, 1) est un mur
    assert obs[IDX_WALLS + window_index(0, -1)] == 1.0  # (1, 0) est un mur
    assert obs[IDX_WALLS + window_index(-2, 0)] == 1.0  # (-1, 1) est hors de la carte
    assert obs[IDX_WALLS + window_index(1, 1)] == 0.0  # (2, 2) est libre


def test_la_fenetre_voit_un_mur_interieur():
    w = monde()
    w.add_wall(7, 6)
    assert observe(w)[IDX_WALLS + window_index(1, 0)] == 1.0


def test_la_fenetre_voit_les_zombies_proches_mais_pas_les_lointains():
    w = monde()
    w.zombies.extend([Zombie(7, 6), Zombie(10, 10)])
    obs = observe(w)
    assert obs[IDX_ZOMBIES + window_index(1, 0)] == 1.0
    assert obs[IDX_ZOMBIES : IDX_ZOMBIES + SIDE * SIDE].sum() == 1.0  # un seul dans la fenêtre


def test_la_fenetre_a_la_taille_prevue():
    assert WINDOW == 2 and SIDE == 5


# ------------------------------------------------------------------ le zombie le plus proche
def test_sans_zombie_les_infos_de_zombie_sont_a_zero():
    obs = observe(monde())
    assert (obs[IDX_NEAREST : IDX_NEAREST + 4] == 0).all()
    assert obs[IDX_COUNT] == 0.0


def test_le_zombie_le_plus_proche_est_decrit_par_rapport_au_joueur():
    w = monde()
    w.zombies.extend([Zombie(9, 6), Zombie(1, 1)])
    obs = observe(w)
    present, dx, dy, distance = obs[IDX_NEAREST : IDX_NEAREST + 4]
    assert present == 1.0
    assert np.isclose(dx, 3 / 12) and dy == 0.0  # 3 cases à droite, même ligne
    assert np.isclose(distance, 3 / 24)
    assert np.isclose(obs[IDX_COUNT], 2 / 5)


# ------------------------------------------------------------------ les objets
def test_l_arme_et_le_medkit_sont_decrits_par_rapport_au_joueur():
    w = monde()
    w.weapon_pos = (9, 6)
    w.medkit_pos = (6, 3)
    obs = observe(w)
    assert obs[IDX_WEAPON] == 1.0
    assert np.isclose(obs[IDX_WEAPON + 1], 3 / 12) and obs[IDX_WEAPON + 2] == 0.0
    assert obs[IDX_MEDKIT] == 1.0
    assert obs[IDX_MEDKIT + 1] == 0.0 and np.isclose(obs[IDX_MEDKIT + 2], -3 / 12)


def test_un_objet_ramasse_disparait_de_l_observation():
    w = monde()
    w.weapon_pos = (7, 6)
    w.step(Action.DROITE)
    assert (observe(w)[IDX_WEAPON : IDX_WEAPON + 3] == 0).all()


# ------------------------------------------------------------------ égocentrique
def test_la_perception_ne_depend_pas_de_la_position_absolue():
    # Même situation (zombie à 3 cases à droite, arme en bas à droite) vue depuis deux endroits
    # différents de la carte : l'agent doit recevoir EXACTEMENT les mêmes nombres.
    a, b = monde(), monde()
    a.player, b.player = (4, 4), (6, 6)
    a.zombies.append(Zombie(7, 4))
    b.zombies.append(Zombie(9, 6))
    a.weapon_pos, b.weapon_pos = (5, 6), (7, 8)
    assert np.array_equal(observe(a), observe(b))