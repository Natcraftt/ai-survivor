"""Tests du benchmark de vitesse (ticket 1.7).

Principe : on ne teste pas des chiffres précis (ils changent d'un PC à l'autre et d'une minute à
l'autre), mais le MÉCANISME : les mesures existent, la comparaison à la référence est juste, la
sauvegarde fonctionne, et la vitesse n'est pas catastrophique.
"""

import contextlib
import io
import tempfile
from pathlib import Path

from survivor import benchmark
from survivor.benchmark import (
    METRIQUES_DE_VITESSE, charger, comparer, formater, main, mesurer_parties, mesurer_pas,
    mesurer_resets, mesurer_tout, sauvegarder,
)

# Un petit benchmark (échelle 0.05) : assez pour tester, assez court pour ne pas ralentir la suite.
PETIT = {"repetitions": 1, "echelle": 0.05}


def sans_affichage(fonction, *args):
    """Exécute fonction(*args) en cachant ce qu'elle affiche, et retourne son résultat."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fonction(*args)


# ------------------------------------------------------------------ les mesures existent
def test_toutes_les_mesures_sont_presentes_et_positives():
    mesures = mesurer_tout(**PETIT)
    attendues = {
        "resets_par_s", "pas_par_s", "pas_politique_par_s", "parties_par_min",
        "longueur_moyenne_partie",
    }
    assert attendues <= set(mesures)
    assert all(valeur > 0 for valeur in mesures.values())


def test_la_mesure_gymnasium_n_existe_que_si_gymnasium_est_installe():
    try:
        import gymnasium  # noqa: F401
        installe = True
    except ImportError:
        installe = False
    assert ("pas_gym_par_s" in mesurer_tout(**PETIT)) == installe


def test_les_parties_mesurees_sont_toujours_les_memes_pour_une_graine():
    # Seul le chronomètre varie : la charge de travail, elle, est identique, donc comparable.
    a = mesurer_parties(n=10, seed=3)
    b = mesurer_parties(n=10, seed=3)
    assert a[1] == b[1]  # même longueur moyenne
    assert mesurer_parties(n=10, seed=4)[1] != a[1]  # une autre graine joue d'autres parties


def test_une_partie_dure_au_plus_le_nombre_de_tours_maximum():
    _, longueur, _ = mesurer_parties(n=20, seed=0)
    assert 0 < longueur <= 150


# ------------------------------------------------------------------ garde-fou grossier de vitesse
def test_le_moteur_n_est_pas_devenu_catastrophiquement_lent():
    # Planchers VOLONTAIREMENT très bas (20 à 100 fois sous la vitesse normale) : ce test
    # n'attrape pas un ralentissement de 20 %, il attrape une catastrophe (par exemple une
    # boucle qui devient quadratique). Les ralentissements fins sont le travail de --check.
    assert mesurer_pas(n=3000) > 20_000
    assert mesurer_resets(n=60) > 100


# ------------------------------------------------------------------ la comparaison à la référence
REFERENCE = {"resets_par_s": 1000.0, "pas_par_s": 500_000.0, "pas_politique_par_s": 100_000.0}


def test_comparer_ne_signale_rien_si_c_est_aussi_rapide_ou_plus():
    assert comparer(dict(REFERENCE), REFERENCE) == []
    plus_rapide = {nom: valeur * 2 for nom, valeur in REFERENCE.items()}
    assert comparer(plus_rapide, REFERENCE) == []


def test_comparer_tolere_un_petit_ralentissement():
    un_peu_plus_lent = {nom: valeur * 0.75 for nom, valeur in REFERENCE.items()}  # -25 %
    assert comparer(un_peu_plus_lent, REFERENCE, tolerance=0.30) == []


def test_comparer_signale_un_vrai_ralentissement():
    actuel = dict(REFERENCE)
    actuel["pas_par_s"] = REFERENCE["pas_par_s"] * 0.60  # -40 %
    assert comparer(actuel, REFERENCE, tolerance=0.30) == [
        ("pas_par_s", 300_000.0, 500_000.0)
    ]


def test_la_tolerance_est_respectee_a_la_limite():
    actuel = dict(REFERENCE)
    actuel["resets_par_s"] = 700.0  # exactement -30 % : accepté
    assert comparer(actuel, REFERENCE, tolerance=0.30) == []
    actuel["resets_par_s"] = 699.0  # un poil plus lent : signalé
    assert [nom for nom, _, _ in comparer(actuel, REFERENCE, tolerance=0.30)] == ["resets_par_s"]


def test_comparer_ignore_les_mesures_absentes_d_un_cote():
    reference = dict(REFERENCE, pas_gym_par_s=40_000.0)
    assert comparer(dict(REFERENCE), reference) == []  # pas de mesure gym actuelle : ignorée
    assert comparer(dict(REFERENCE, pas_gym_par_s=1.0), REFERENCE) == []  # pas de référence gym


def test_comparer_ne_juge_pas_les_mesures_qui_ne_sont_pas_des_vitesses():
    # parties/min et longueur moyenne dépendent des règles du jeu, pas seulement du code.
    reference = dict(REFERENCE, parties_par_min=100_000.0, longueur_moyenne_partie=50.0)
    actuel = dict(REFERENCE, parties_par_min=1.0, longueur_moyenne_partie=5000.0)
    assert comparer(actuel, reference) == []
    assert "parties_par_min" not in METRIQUES_DE_VITESSE


# ------------------------------------------------------------------ sauvegarde et chargement
def test_sauvegarder_puis_charger_redonne_les_memes_mesures():
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "benchmarks" / "baseline.json"  # le sous-dossier n'existe pas encore
        sauvegarder(REFERENCE, chemin)
        assert charger(chemin) == REFERENCE


# ------------------------------------------------------------------ l'affichage
def test_formater_montre_chaque_mesure_et_l_ecart_avec_la_reference():
    texte = formater({"pas_par_s": 600_000.0}, {"pas_par_s": 500_000.0})
    assert "pas_par_s" in texte
    assert "+20 %" in texte
    assert "%" not in formater({"pas_par_s": 600_000.0})  # sans référence, pas d'écart


# ------------------------------------------------------------------ la ligne de commande
def test_save_puis_check_reussit():
    with tempfile.TemporaryDirectory() as dossier:
        base = str(Path(dossier) / "ref.json")
        options = ["--repetitions", "1", "--echelle", "0.05", "--baseline", base]
        assert sans_affichage(main, ["--save", *options]) == 0
        # Tolérance énorme : on teste le mécanisme, pas la stabilité du chronomètre.
        assert sans_affichage(main, ["--check", "--tolerance", "0.95", *options]) == 0


def test_check_echoue_avec_le_code_1_si_la_reference_est_irrealiste():
    with tempfile.TemporaryDirectory() as dossier:
        base = Path(dossier) / "ref.json"
        sauvegarder({nom: 1e12 for nom in METRIQUES_DE_VITESSE}, base)  # personne n'ira aussi vite
        options = ["--repetitions", "1", "--echelle", "0.05", "--baseline", str(base)]
        assert sans_affichage(main, ["--check", *options]) == 1


def test_check_sans_reference_donne_le_code_2():
    with tempfile.TemporaryDirectory() as dossier:
        options = ["--baseline", str(Path(dossier) / "absente.json")]
        assert sans_affichage(main, ["--check", *options]) == 2


def test_le_module_s_appelle_bien_benchmark_et_a_une_reference_par_defaut():
    assert benchmark.REFERENCE_PAR_DEFAUT == Path("benchmarks/baseline.json")