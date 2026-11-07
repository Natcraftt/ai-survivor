"""Tests des tickets 1.1 (boucle), 1.2 (carte, murs, collisions) et 1.3 (zombies)."""

import ast
from pathlib import Path

import survivor.world as world_module
from survivor.actions import MOVES, Action
from survivor.world import World, WorldConfig, Zombie, manhattan

ATTENDRE = Action.ATTENDRE


def monde(seed=0, **reglages):
    """Monde de test. Par défaut : aucun zombie au départ et aucune apparition."""
    base = {"n_zombies": 0, "spawn_prob": 0.0}
    base.update(reglages)
    return World(WorldConfig(**base), seed=seed)


def jouer(world, n, action=ATTENDRE):
    for _ in range(n):
        world.step(action)


def leve(exception, fonction, *args):
    """Vrai si fonction(*args) lève l'exception attendue."""
    try:
        fonction(*args)
    except exception:
        return True
    return False


# ================================================================== ticket 1.1
def test_monde_neuf_est_au_tour_zero_et_pas_fini():
    w = World(seed=0)
    assert w.nb_tours == 0
    assert not w.is_done()


def test_un_step_ajoute_exactement_un_tour():
    w = monde()
    jouer(w, 1)
    assert w.nb_tours == 1
    jouer(w, 1)
    assert w.nb_tours == 2


def test_la_partie_n_est_pas_finie_au_tour_149():
    w = monde()
    jouer(w, w.config.max_steps - 1)
    assert not w.is_done()


def test_la_partie_est_finie_apres_150_tours():
    w = monde()
    jouer(w, 150)
    assert w.nb_tours == 150
    assert w.is_done()


def test_jouer_apres_la_fin_de_partie_leve_une_erreur():
    w = monde()
    jouer(w, 150)
    assert leve(RuntimeError, w.step, ATTENDRE)
    assert w.nb_tours == 150  # le compteur n'a pas bougé


def test_le_moteur_n_importe_aucune_bibliotheque_graphique():
    interdits = {
        "pygame", "tkinter", "turtle", "matplotlib", "pyglet", "arcade", "PyQt5", "PyQt6", "PySide6",
    }
    arbre = ast.parse(Path(world_module.__file__).read_text(encoding="utf-8"))
    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            importes.add(noeud.module.split(".")[0])
    assert importes.isdisjoint(interdits), f"imports graphiques trouvés : {importes & interdits}"


# ================================================================== ticket 1.2 : la carte
def test_la_bordure_est_entierement_en_mur():
    w = monde()
    n = w.size
    for i in range(n):
        assert not w.is_free(i, 0)
        assert not w.is_free(i, n - 1)
        assert not w.is_free(0, i)
        assert not w.is_free(n - 1, i)


def test_l_interieur_est_libre_et_le_joueur_est_au_centre():
    w = monde()
    assert w.player == (6, 6)
    assert w.is_free(6, 6)
    assert all(w.is_free(x, y) for x in range(1, 11) for y in range(1, 11))


def test_is_free_refuse_les_cases_hors_grille_y_compris_negatives():
    w = monde()
    for x, y in [(-1, 5), (5, -1), (-1, -1), (12, 5), (5, 12), (100, 100)]:
        assert not w.is_free(x, y)


# ================================================================== ticket 1.2 : les déplacements
def test_chaque_direction_deplace_le_joueur_d_une_case():
    attendu = {
        Action.HAUT: (6, 5),
        Action.DROITE: (7, 6),
        Action.BAS: (6, 7),
        Action.GAUCHE: (5, 6),
    }
    for action, position in attendu.items():
        w = monde()
        w.step(action)
        assert w.player == position, action


def test_les_decalages_correspondent_aux_directions():
    assert MOVES[Action.HAUT] == (0, -1)
    assert MOVES[Action.BAS] == (0, 1)
    assert MOVES[Action.GAUCHE] == (-1, 0)
    assert MOVES[Action.DROITE] == (1, 0)
    assert ATTENDRE not in MOVES


def test_attendre_ne_bouge_pas_mais_le_tour_avance():
    w = monde()
    w.step(ATTENDRE)
    assert w.player == (6, 6)
    assert w.nb_tours == 1


def test_marcher_vers_un_mur_ne_bouge_pas_mais_le_tour_avance():
    w = monde()
    w.add_wall(7, 6)
    w.step(Action.DROITE)
    assert w.player == (6, 6)
    assert w.nb_tours == 1


def test_le_joueur_ne_sort_jamais_de_la_grille():
    for action in (Action.HAUT, Action.DROITE, Action.BAS, Action.GAUCHE):
        w = monde()
        jouer(w, 30, action)
        x, y = w.player
        assert w.is_free(x, y), action
        assert 1 <= x <= w.size - 2 and 1 <= y <= w.size - 2, action


def test_le_joueur_s_arrete_dans_un_angle():
    w = monde()
    jouer(w, 20, Action.HAUT)
    jouer(w, 20, Action.GAUCHE)
    assert w.player == (1, 1)


def test_un_numero_d_action_inexistant_leve_une_erreur():
    w = monde()
    assert leve(ValueError, w.step, 99)
    assert w.nb_tours == 0  # rien ne s'est passé


def test_add_wall_refuse_hors_grille_sur_le_joueur_et_sur_un_zombie():
    w = monde()
    w.zombies.append(Zombie(9, 9))
    assert leve(ValueError, w.add_wall, -1, 3)
    assert leve(ValueError, w.add_wall, 3, 12)
    assert leve(ValueError, w.add_wall, 6, 6)
    assert leve(ValueError, w.add_wall, 9, 9)


# ================================================================== ticket 1.3 : zombies au départ
def test_un_monde_neuf_contient_deux_zombies_bien_places():
    for seed in range(20):
        w = World(seed=seed)
        positions = [(z.x, z.y) for z in w.zombies]
        assert len(positions) == 2, seed
        assert len(set(positions)) == 2, seed  # cases distinctes
        for x, y in positions:
            assert w.is_free(x, y), seed
            assert manhattan((x, y), w.player) >= w.config.min_spawn_distance, seed


def test_le_joueur_commence_avec_tous_ses_pv():
    w = World(seed=0)
    assert w.hp == w.config.max_hp == 5


def test_meme_graine_memes_zombies_graines_differentes_cartes_differentes():
    a, b = World(seed=7), World(seed=7)
    assert a.to_dict() == b.to_dict()
    positions = {tuple((z.x, z.y) for z in World(seed=s).zombies) for s in range(10)}
    assert len(positions) > 1


def test_une_partie_rejouee_avec_la_meme_graine_est_identique():
    reglages = {"n_zombies": 3, "spawn_prob": 0.2, "zombie_move_prob": 0.8, "max_hp": 1000}
    suite = [Action.HAUT, Action.DROITE, Action.BAS, Action.GAUCHE, ATTENDRE] * 20
    a, b = monde(seed=3, **reglages), monde(seed=3, **reglages)
    for action in suite:
        a.step(action)
        b.step(action)
        assert a.to_dict() == b.to_dict()


def test_reset_avec_graine_redonne_le_meme_monde():
    w = World(WorldConfig(max_hp=1000), seed=5)  # beaucoup de PV : on veut jouer 20 tours
    depart = w.to_dict()
    jouer(w, 20)
    w.reset(seed=5)
    assert w.to_dict() == depart


# ================================================================== ticket 1.3 : poursuite
def test_un_zombie_eloigne_se_rapproche_d_une_case_par_tour():
    w = monde(zombie_move_prob=1.0)
    w.zombies.append(Zombie(10, 6))
    distances = []
    for _ in range(3):
        w.step(ATTENDRE)
        distances.append(manhattan((w.zombies[0].x, w.zombies[0].y), w.player))
    assert distances == [3, 2, 1]


def test_un_zombie_avec_probabilite_zero_ne_bouge_jamais():
    w = monde(zombie_move_prob=0.0)
    w.zombies.append(Zombie(10, 6))
    jouer(w, 10)
    assert (w.zombies[0].x, w.zombies[0].y) == (10, 6)


def test_un_zombie_ne_traverse_pas_un_mur():
    w = monde(zombie_move_prob=1.0)
    w.add_wall(7, 6)
    w.zombies.append(Zombie(8, 6))
    jouer(w, 5)
    assert (w.zombies[0].x, w.zombies[0].y) == (8, 6)  # coincé derrière le mur


def test_un_zombie_bloque_sur_un_axe_essaie_l_autre():
    w = monde(zombie_move_prob=1.0)
    w.add_wall(7, 5)
    w.zombies.append(Zombie(8, 5))
    w.step(ATTENDRE)
    assert (w.zombies[0].x, w.zombies[0].y) == (8, 6)


def test_un_zombie_ne_se_superpose_pas_a_un_autre_zombie():
    w = monde(zombie_move_prob=1.0, max_hp=1000)
    w.zombies.extend([Zombie(8, 6), Zombie(7, 6)])  # le second est collé au joueur
    w.step(ATTENDRE)
    assert (w.zombies[0].x, w.zombies[0].y) == (8, 6)  # bloqué par le second
    assert (w.zombies[1].x, w.zombies[1].y) == (7, 6)


def test_un_zombie_ne_marche_jamais_sur_le_joueur():
    w = monde(zombie_move_prob=1.0, max_hp=1000)
    w.zombies.append(Zombie(8, 6))
    jouer(w, 20)
    assert (w.zombies[0].x, w.zombies[0].y) != w.player


def test_le_joueur_ne_peut_pas_marcher_dans_un_zombie():
    w = monde(zombie_move_prob=0.0)
    w.zombies.append(Zombie(7, 6))
    w.step(Action.DROITE)
    assert w.player == (6, 6)
    assert w.nb_tours == 1


# ================================================================== ticket 1.3 : attaque et mort
def test_un_zombie_adjacent_attaque_et_ne_bouge_pas():
    w = monde(zombie_move_prob=1.0)
    w.zombies.append(Zombie(7, 6))
    w.step(ATTENDRE)
    assert w.hp == 4
    assert (w.zombies[0].x, w.zombies[0].y) == (7, 6)


def test_le_joueur_perd_un_pv_par_tour_puis_la_partie_est_finie_a_zero():
    w = monde(zombie_move_prob=1.0)
    w.zombies.append(Zombie(7, 6))
    jouer(w, 4)
    assert w.hp == 1 and not w.is_done()
    w.step(ATTENDRE)
    assert w.hp == 0
    assert w.dead and w.is_done()
    assert w.nb_tours == 5  # fini bien avant les 150 tours
    assert leve(RuntimeError, w.step, ATTENDRE)


def test_les_pv_ne_descendent_jamais_sous_zero():
    w = monde(zombie_move_prob=1.0, max_hp=1, zombie_damage=3)
    w.zombies.append(Zombie(7, 6))
    w.step(ATTENDRE)
    assert w.hp == 0


def test_le_joueur_agit_avant_les_zombies_s_approcher_coute_un_pv():
    w = monde(zombie_move_prob=1.0)
    w.zombies.append(Zombie(8, 6))
    w.step(Action.DROITE)  # le joueur va en (7, 6), collé au zombie, qui frappe aussitôt
    assert w.player == (7, 6)
    assert w.hp == 4


def test_le_joueur_agit_avant_les_zombies_fuir_un_zombie_adjacent_ne_coute_rien():
    w = monde(zombie_move_prob=1.0)
    w.zombies.append(Zombie(7, 6))
    w.step(Action.GAUCHE)  # le joueur recule en (5, 6) avant que le zombie n'agisse
    assert w.hp == 5
    assert (w.zombies[0].x, w.zombies[0].y) == (6, 6)  # le zombie a suivi


# ================================================================== ticket 1.3 : apparitions
def test_avec_probabilite_un_un_zombie_apparait_a_chaque_tour_loin_du_joueur():
    w = monde(spawn_prob=1.0, zombie_move_prob=0.0, max_zombies=5)
    for attendu in (1, 2, 3):
        w.step(ATTENDRE)
        assert len(w.zombies) == attendu
        z = w.zombies[-1]
        assert w.is_free(z.x, z.y)
        assert manhattan((z.x, z.y), w.player) >= w.config.min_spawn_distance


def test_le_nombre_de_zombies_ne_depasse_jamais_le_maximum():
    w = monde(spawn_prob=1.0, zombie_move_prob=0.0, max_zombies=3)
    jouer(w, 10)
    assert len(w.zombies) == 3


def test_avec_probabilite_zero_aucun_zombie_n_apparait():
    w = monde(spawn_prob=0.0)
    jouer(w, 100)
    assert w.zombies == []


def test_les_zombies_apparus_ne_sont_jamais_sur_la_meme_case():
    w = monde(spawn_prob=1.0, zombie_move_prob=0.0, max_zombies=5)
    jouer(w, 5)
    positions = [(z.x, z.y) for z in w.zombies]
    assert len(set(positions)) == len(positions) == 5


# ================================================================== sauvegarde et reset
def test_export_puis_reconstruction_donne_le_meme_monde():
    w = World(seed=4)
    w.add_wall(3, 3)
    w.step(Action.GAUCHE)
    w.step(Action.HAUT)
    data = w.to_dict()

    copie = World(seed=999)
    copie.from_dict(data)

    assert copie.to_dict() == data
    assert copie.player == w.player
    assert not copie.is_free(3, 3)
    assert [(z.x, z.y, z.hp) for z in copie.zombies] == [(z.x, z.y, z.hp) for z in w.zombies]


def test_l_export_est_independant_du_monde():
    w = monde()
    w.zombies.append(Zombie(9, 9))
    data = w.to_dict()
    w.add_wall(3, 3)
    w.step(Action.DROITE)
    w.zombies[0].x = 2
    assert data["walls"][3][3] is False
    assert data["player"] == [6, 6]
    assert data["nb_tours"] == 0
    assert data["zombies"][0]["x"] == 9


def test_le_monde_reconstruit_est_independant_des_donnees():
    w = monde()
    w.zombies.append(Zombie(9, 9))
    data = w.to_dict()
    copie = World()
    copie.from_dict(data)
    data["walls"][3][3] = True
    data["zombies"][0]["x"] = 2
    assert copie.is_free(3, 3)
    assert copie.zombies[0].x == 9


def test_reset_remet_la_carte_les_pv_et_les_zombies_a_zero():
    w = World(seed=1)
    w.add_wall(3, 3)
    jouer(w, 5, Action.DROITE)
    w.hp = 1
    w.reset()
    assert w.nb_tours == 0
    assert w.player == (6, 6)
    assert w.hp == w.config.max_hp
    assert w.is_free(3, 3)
    assert len(w.zombies) == 2
    assert not w.is_done()


def test_la_taille_est_configurable():
    w = monde(size=5)
    assert w.player == (2, 2)
    assert not w.is_free(0, 0)
    assert not w.is_free(5, 2)
    assert w.is_free(1, 1) and w.is_free(3, 3)