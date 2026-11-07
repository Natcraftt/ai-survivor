"""Tests du ticket 1.1 : boucle de simulation sans fenêtre."""

import ast
from pathlib import Path

import survivor.world as world_module
from survivor.world import World

ACTION_QUELCONQUE = 0  # pour l'instant, step ignore l'action


def jouer(world, n):
    for _ in range(n):
        world.step(ACTION_QUELCONQUE)


def test_monde_neuf_est_au_tour_zero_et_pas_fini():
    w = World()
    assert w.nb_tours == 0
    assert not w.is_done()


def test_un_step_ajoute_exactement_un_tour():
    w = World()
    jouer(w, 1)
    assert w.nb_tours == 1
    jouer(w, 1)
    assert w.nb_tours == 2


def test_la_partie_n_est_pas_finie_au_tour_149():
    w = World()
    jouer(w, World.NB_MAX_TOUR - 1)
    assert not w.is_done()


def test_la_partie_est_finie_apres_150_tours():
    w = World()
    jouer(w, 150)
    assert w.nb_tours == 150
    assert w.is_done()


def test_reset_remet_le_monde_a_zero():
    w = World()
    jouer(w, 150)
    w.reset()
    assert w.nb_tours == 0
    assert not w.is_done()


def test_export_puis_reconstruction_donne_le_meme_etat():
    w = World()
    jouer(w, 42)
    data = w.to_dict()

    copie = World()
    copie.from_dict(data)

    assert copie.to_dict() == data
    assert copie.nb_tours == 42


def test_l_export_est_independant_du_monde():
    # Modifier le monde après l'export ne doit pas changer l'export déjà fait.
    w = World()
    jouer(w, 5)
    data = w.to_dict()
    jouer(w, 5)
    assert data["nb_tours"] == 5


def test_le_moteur_n_importe_aucune_bibliotheque_graphique():
    interdits = {"pygame", "tkinter", "turtle", "matplotlib", "pyglet", "arcade", "PyQt5", "PyQt6", "PySide6"}
    arbre = ast.parse(Path(world_module.__file__).read_text(encoding="utf-8"))
    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            importes.add(noeud.module.split(".")[0])
    assert importes.isdisjoint(interdits), f"imports graphiques trouvés : {importes & interdits}"