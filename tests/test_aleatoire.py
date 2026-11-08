"""Tests du ticket 1.5 : aléatoire seedé (cartes variées, graine par partie, hasard exportable).

Idée directrice : le hasard doit être À LA FOIS
  - varié        : chaque partie a une carte différente (l'IA apprend des principes) ;
  - reproductible : avec la même graine, tout se rejoue à l'identique (on peut déboguer).
"""

import copy
import json
import random
from collections import deque

from survivor.actions import MOVES, Action
from survivor.world import World, WorldConfig


def murs_interieurs(w):
    n = w.size
    return sum(w.walls[y][x] for y in range(1, n - 1) for x in range(1, n - 1))


def cases_atteignables(w):
    """Cases où le joueur peut aller en marchant. Écrit ici, indépendamment du code testé."""
    vues = {w.player}
    a_visiter = deque([w.player])
    while a_visiter:
        x, y = a_visiter.popleft()
        for dx, dy in MOVES.values():
            case = (x + dx, y + dy)
            if w.is_free(*case) and case not in vues:
                vues.add(case)
                a_visiter.append(case)
    return vues


def cases_libres(w):
    return {(x, y) for y in range(w.size) for x in range(w.size) if w.is_free(x, y)}


def carte(w):
    """Résumé comparable de la carte d'une partie."""
    return (tuple(map(tuple, w.walls)), w.player)


# ================================================================== cartes aléatoires
def test_la_densite_de_murs_est_respectee_en_moyenne():
    # 200 cartes avec la densité par défaut (0.12) : la part de murs doit être proche de 12 %.
    parts = []
    for seed in range(200):
        w = World(seed=seed)
        cases_interieures = (w.size - 2) ** 2
        parts.append(murs_interieurs(w) / cases_interieures)
    moyenne = sum(parts) / len(parts)
    assert 0.08 < moyenne < 0.16, moyenne


def test_densite_zero_donne_une_arene_vide():
    for seed in range(20):
        w = World(WorldConfig(wall_density=0.0), seed=seed)
        assert murs_interieurs(w) == 0


def test_toutes_les_cases_libres_sont_reliees_au_joueur():
    # Densité énorme (0.3) pour mettre le générateur à l'épreuve : sans la vérification de
    # connexion, des poches fermées apparaîtraient souvent.
    for seed in range(100):
        w = World(WorldConfig(wall_density=0.3), seed=seed)
        assert cases_atteignables(w) == cases_libres(w), seed


def test_joueur_zombies_et_objets_sont_tous_atteignables():
    for seed in range(100):
        w = World(WorldConfig(wall_density=0.25), seed=seed)
        accessibles = cases_atteignables(w)
        positions = [(z.x, z.y) for z in w.zombies] + [w.weapon_pos, w.medkit_pos]
        for p in positions:
            assert p in accessibles, (seed, p)


def test_une_densite_impossible_retombe_sur_une_arene_vide():
    # Densité 1.0 : tout est mur, aucune carte valide. Le monde ne plante pas : arène vide.
    w = World(WorldConfig(wall_density=1.0, random_start=True), seed=0)
    assert murs_interieurs(w) == 0
    assert w.is_free(*w.player)


def test_une_carte_minuscule_reste_jouable():
    for seed in range(30):
        w = World(WorldConfig(size=3), seed=seed)
        assert w.player == (1, 1) and w.is_free(1, 1)


def test_meme_graine_meme_carte_graines_differentes_cartes_differentes():
    assert carte(World(seed=7)) == carte(World(seed=7))
    cartes = {carte(World(seed=s)) for s in range(20)}
    assert len(cartes) == 20  # 20 graines, 20 cartes distinctes


# ================================================================== départ aléatoire
def test_le_joueur_demarre_sur_une_case_libre_et_pas_toujours_au_meme_endroit():
    departs = set()
    for seed in range(50):
        w = World(seed=seed)
        assert w.is_free(*w.player)
        departs.add(w.player)
    assert len(departs) > 10


def test_random_start_false_garde_le_joueur_au_centre_meme_avec_des_murs():
    for seed in range(30):
        w = World(WorldConfig(wall_density=0.3, random_start=False), seed=seed)
        assert w.player == (6, 6)
        assert w.is_free(6, 6)  # le centre est dégagé même si un mur y était tiré


# ================================================================== une graine par partie
def test_la_premiere_partie_utilise_la_graine_donnee():
    assert World(seed=5).seed == 5


def test_sans_graine_le_monde_en_choisit_une():
    w = World()
    assert isinstance(w.seed, int)


def test_les_parties_successives_sont_differentes():
    w = World(seed=3)
    graines, cartes = [w.seed], [carte(w)]
    for _ in range(9):
        w.reset()  # sans argument : nouvelle partie
        graines.append(w.seed)
        cartes.append(carte(w))
    assert len(set(graines)) == 10
    assert len(set(cartes)) == 10


def test_la_suite_de_parties_est_reproductible():
    a, b = World(seed=3), World(seed=3)
    for _ in range(5):
        a.reset()
        b.reset()
        assert a.to_dict() == b.to_dict()


def test_une_partie_se_rejoue_avec_sa_graine():
    # Le scénario de débogage : « la partie n°37 a bugué » -> on relève sa graine et on la rejoue.
    w = World(seed=3)
    for _ in range(4):
        w.reset()
    graine, etat = w.seed, w.to_dict()

    rejeu = World(seed=999)
    rejeu.reset(seed=graine)
    assert rejeu.to_dict()["walls"] == etat["walls"]
    assert rejeu.to_dict()["zombies"] == etat["zombies"]
    assert rejeu.to_dict()["player"] == etat["player"]
    assert rejeu.to_dict()["rng_state"] == etat["rng_state"]


def test_donner_une_graine_a_reset_ne_decale_pas_la_suite_des_parties():
    a, b = World(seed=1), World(seed=1)
    a.reset(seed=42)  # partie imposée : ne consomme rien de la suite de graines
    a.reset()
    b.reset()
    assert a.seed == b.seed


# ================================================================== le hasard dans l'export
def jouer_une_suite(w, nombre):
    """Une suite fixe d'actions (toujours la même) pour comparer deux mondes."""
    actions = [Action.HAUT, Action.DROITE, Action.ATTAQUER, Action.BAS, Action.GAUCHE, Action.ATTENDRE]
    for i in range(nombre):
        if not w.is_done():
            w.step(actions[i % len(actions)])


def test_un_monde_reconstruit_rejoue_exactement_la_meme_suite():
    # Le test central du ticket : après export puis reconstruction, les deux mondes doivent
    # évoluer de façon IDENTIQUE, y compris le hasard (mouvements et apparitions de zombies).
    config = WorldConfig(max_hp=1000, spawn_prob=0.2, zombie_move_prob=0.7)
    original = World(config, seed=11)
    jouer_une_suite(original, 20)

    copie = World()
    copie.from_dict(original.to_dict())

    for _ in range(60):
        jouer_une_suite(original, 1)
        jouer_une_suite(copie, 1)
        assert copie.to_dict() == original.to_dict()


def test_apres_reconstruction_la_partie_suivante_est_la_meme_aussi():
    original = World(seed=8)
    jouer_une_suite(original, 10)
    copie = World()
    copie.from_dict(original.to_dict())
    original.reset()
    copie.reset()
    assert copie.to_dict() == original.to_dict()


def test_l_export_passe_par_json_sans_rien_perdre():
    # to_dict doit être « sérialisable » (ticket 1.1) : on l'écrit en texte JSON et on le relit.
    original = World(seed=21)
    jouer_une_suite(original, 15)
    texte = json.dumps(original.to_dict())
    copie = World()
    copie.from_dict(json.loads(texte))
    assert copie.to_dict() == original.to_dict()
    jouer_une_suite(original, 20)
    jouer_une_suite(copie, 20)
    assert copie.to_dict() == original.to_dict()


def test_l_export_est_un_instantane_independant():
    w = World(WorldConfig(max_hp=1000), seed=2)
    data = w.to_dict()
    avant = copy.deepcopy(data)
    jouer_une_suite(w, 30)  # le hasard avance dans le monde...
    assert data == avant  # ...mais l'export déjà fait n'a pas bougé


def test_les_donnees_modifiees_apres_reconstruction_ne_changent_pas_le_monde():
    w = World(seed=2)
    data = w.to_dict()
    copie = World()
    copie.from_dict(data)
    etat = copy.deepcopy(copie.to_dict())
    data["rng_state"][1][0] += 1
    data["seeder_state"][1][0] += 1
    assert copie.to_dict() == etat


# ================================================================== test d'ensemble
def test_parties_aleatoires_completes_sans_erreur_et_toujours_reproductibles():
    # 60 parties jouées au hasard avec des cartes variées ; chaque partie est rejouée à
    # l'identique à partir de sa seule graine.
    for seed in range(60):
        config = WorldConfig(wall_density=0.2)
        w = World(config, seed=seed)
        choix = random.Random(seed)
        actions = [choix.choice(list(Action)) for _ in range(150)]
        for a in actions:
            if w.is_done():
                break
            w.step(a)

        rejeu = World(config, seed=seed)
        for a in actions:
            if rejeu.is_done():
                break
            rejeu.step(a)
        assert rejeu.to_dict() == w.to_dict(), seed