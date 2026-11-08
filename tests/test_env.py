"""Tests de l'interface Gymnasium (ticket 1.6).

Ce fichier est ignoré automatiquement si gymnasium n'est pas installé (pip install gymnasium).
"""

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from survivor.actions import N_ACTIONS, Action  # noqa: E402
from survivor.env import SurvivalEnv  # noqa: E402
from survivor.reward import MORT, SURVIE  # noqa: E402
from survivor.world import WorldConfig, Zombie  # noqa: E402


def env_calme(**reglages):
    """Environnement sans zombie : le joueur survit toujours jusqu'à la limite de tours."""
    base = {"n_zombies": 0, "spawn_prob": 0.0}
    base.update(reglages)
    return SurvivalEnv(WorldConfig(**base))


def test_l_environnement_respecte_la_norme_gymnasium():
    # check_env est le vérificateur officiel de Gymnasium : si ce test passe, l'environnement
    # parle correctement le langage standard et les algorithmes pourront s'y brancher.
    from gymnasium.utils.env_checker import check_env

    check_env(SurvivalEnv(), skip_render_check=True)


def test_les_espaces_ont_la_bonne_forme():
    env = SurvivalEnv()
    assert env.action_space.n == N_ACTIONS == 7
    assert env.observation_space.shape == (64,)
    assert env.observation_space.dtype == np.float32


def test_reset_renvoie_une_observation_valide_et_des_infos():
    env = SurvivalEnv()
    obs, info = env.reset(seed=1)
    assert env.observation_space.contains(obs)
    assert info["hp"] == 5 and info["nb_tours"] == 0
    assert info["seed"] == env.world.seed


def test_meme_graine_meme_premiere_partie():
    a, b = SurvivalEnv(), SurvivalEnv()
    obs_a, _ = a.reset(seed=42)
    obs_b, _ = b.reset(seed=42)
    assert np.array_equal(obs_a, obs_b)
    assert a.world.to_dict() == b.world.to_dict()


def test_graines_differentes_parties_differentes():
    env = SurvivalEnv()
    departs = set()
    for graine in range(10):
        env.reset(seed=graine)
        departs.add((tuple(map(tuple, env.world.walls)), env.world.player))
    assert len(departs) == 10


def test_les_resets_suivants_sans_graine_donnent_des_parties_differentes_mais_reproductibles():
    a, b = SurvivalEnv(), SurvivalEnv()
    a.reset(seed=5)
    b.reset(seed=5)
    suite_a, suite_b = [], []
    for _ in range(5):
        a.reset()
        b.reset()
        suite_a.append(a.world.seed)
        suite_b.append(b.world.seed)
    assert suite_a == suite_b  # reproductible
    assert len(set(suite_a)) == 5  # mais chaque partie est différente


def test_step_renvoie_cinq_valeurs_du_bon_type():
    env = env_calme()
    env.reset(seed=0)
    obs, reward, terminated, truncated, info = env.step(Action.ATTENDRE)
    assert env.observation_space.contains(obs)
    assert reward == SURVIE
    assert terminated is False and truncated is False
    assert info["nb_tours"] == 1


def test_survivre_jusqu_a_la_limite_donne_truncated_et_pas_terminated():
    env = env_calme()
    env.reset(seed=0)
    for tour in range(150):
        _, reward, terminated, truncated, _ = env.step(Action.ATTENDRE)
        assert reward == SURVIE and not terminated
        assert truncated == (tour == 149)  # vrai uniquement au 150e tour


def test_mourir_donne_terminated_et_la_penalite_de_mort():
    env = env_calme(max_hp=1, wall_density=0.0, random_start=False)
    env.reset(seed=0)
    env.world.zombies.append(Zombie(7, 6))  # adjacent au joueur placé au centre
    _, reward, terminated, truncated, info = env.step(Action.ATTENDRE)
    assert terminated is True and truncated is False
    assert reward == MORT
    assert info["hp"] == 0


def test_jouer_apres_la_fin_sans_reset_leve_une_erreur():
    env = env_calme(max_steps=1)
    env.reset(seed=0)
    env.step(Action.ATTENDRE)
    with pytest.raises(RuntimeError):
        env.step(Action.ATTENDRE)


def test_un_nouveau_reset_permet_de_rejouer_apres_la_fin():
    env = env_calme(max_steps=1)
    env.reset(seed=0)
    env.step(Action.ATTENDRE)
    env.reset()
    _, _, terminated, truncated, info = env.step(Action.ATTENDRE)
    assert info["nb_tours"] == 1 and truncated is True and terminated is False


def test_le_masque_d_actions_vient_du_monde():
    env = SurvivalEnv()
    env.reset(seed=3)
    masque = env.action_masks()
    assert masque.dtype == bool and masque.shape == (N_ACTIONS,)
    assert list(masque) == env.world.action_mask()


def test_une_partie_entiere_avec_le_masque_se_termine_et_reste_valide():
    env = SurvivalEnv()
    hasard = np.random.default_rng(0)
    for graine in range(10):
        obs, _ = env.reset(seed=graine)
        fini = False
        pas = 0
        while not fini:
            valides = np.flatnonzero(env.action_masks())
            action = int(hasard.choice(valides))
            obs, reward, terminated, truncated, _ = env.step(action)
            assert env.observation_space.contains(obs)
            fini = terminated or truncated
            pas += 1
        assert pas <= 150