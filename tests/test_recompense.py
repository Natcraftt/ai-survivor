"""Tests de la récompense minimale (ticket 1.6)."""

from survivor.actions import Action
from survivor.reward import MORT, SURVIE, compute_reward
from survivor.world import World, WorldConfig, Zombie


def test_survivre_rapporte_et_mourir_coute_cher():
    assert SURVIE > 0 > MORT
    assert abs(MORT) > SURVIE  # mourir doit coûter plus que ce qu'un tour rapporte


def test_en_vie_la_recompense_est_celle_de_survie():
    w = World(WorldConfig(n_zombies=0, spawn_prob=0.0), seed=0)
    w.step(Action.ATTENDRE)
    assert compute_reward(w) == SURVIE


def test_a_la_mort_la_recompense_est_celle_de_la_mort():
    w = World(WorldConfig(n_zombies=0, spawn_prob=0.0, max_hp=1, wall_density=0.0, random_start=False), seed=0)
    w.zombies.append(Zombie(7, 6))  # adjacent au joueur placé au centre
    w.step(Action.ATTENDRE)
    assert w.dead
    assert compute_reward(w) == MORT