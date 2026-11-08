"""Benchmark de vitesse du moteur (ticket 1.7).

Pourquoi : entraîner une IA demande des milliers de parties. Si le moteur est lent, l'entraînement
l'est aussi. Ce module mesure la vitesse, et sert de garde-fou : si une modification future
ralentit le jeu, on le voit tout de suite au lieu de le découvrir au bout d'une nuit d'entraînement.

Utilisation, depuis la racine du projet :
    python -m survivor.benchmark            # mesure et affiche
    python -m survivor.benchmark --save     # enregistre ces chiffres comme référence
    python -m survivor.benchmark --check    # compare à la référence, code de sortie 1 si trop lent

Les chiffres dépendent de la machine : la référence enregistrée n'est valable que sur le PC qui
l'a produite. Sur une autre machine, refais un --save.
"""

import argparse
import json
import platform
import random
import time
from pathlib import Path

from .actions import N_ACTIONS
from .world import World, WorldConfig

# Où ranger la référence par défaut (relatif au dossier où on lance la commande).
REFERENCE_PAR_DEFAUT = Path("benchmarks/baseline.json")

# Les mesures de VITESSE : plus c'est haut, mieux c'est. Seules celles-ci sont comparées.
# (parties_par_min et longueur_moyenne_partie sont affichées pour information : elles dépendent
# aussi des règles du jeu, pas seulement de la vitesse du code.)
METRIQUES_DE_VITESSE = ("resets_par_s", "pas_par_s", "pas_politique_par_s", "pas_gym_par_s")

# Nombre de répétitions de base de chaque mesure (multiplié par --echelle).
N_RESETS = 1000
N_PAS = 20_000
N_PARTIES = 100
N_PAS_GYM = 5_000


def _combien(base, echelle):
    return max(5, int(base * echelle))


def _actions_au_hasard(seed, nombre=1000):
    """Suite d'actions tirée AVANT de lancer le chronomètre : on ne mesure pas le tirage."""
    hasard = random.Random(seed)
    return [hasard.randrange(N_ACTIONS) for _ in range(nombre)]


# ---------------------------------------------------------------------------- les mesures
def mesurer_resets(n=N_RESETS, seed=0):
    """Cartes générées par seconde. Compte, car on lance beaucoup de parties courtes."""
    monde = World(seed=seed)
    debut = time.perf_counter()
    for _ in range(n):
        monde.reset()
    return n / (time.perf_counter() - debut)


def mesurer_pas(n=N_PAS, seed=0):
    """Tours par seconde du moteur seul, sans aucune IA ni observation.

    Le joueur est quasi invincible et la partie ne s'arrête jamais : on mesure uniquement step(),
    sans que la mort ou la fin de partie n'interrompe la boucle.
    """
    monde = World(WorldConfig(max_hp=10**9, max_steps=10**9), seed=seed)
    actions = _actions_au_hasard(seed)
    debut = time.perf_counter()
    for i in range(n):
        monde.step(actions[i % len(actions)])
    return n / (time.perf_counter() - debut)


def mesurer_parties(n=N_PARTIES, seed=0):
    """Parties complètes jouées par un joueur aléatoire qui consulte le masque d'actions.

    Retourne (parties par minute, longueur moyenne d'une partie, tours par seconde).
    Les parties sont toujours les mêmes pour une graine donnée : seul le temps varie, donc les
    mesures sont comparables d'une fois sur l'autre.
    """
    monde = World(seed=seed)
    hasard = random.Random(seed)
    pas = 0
    debut = time.perf_counter()
    for _ in range(n):
        monde.reset()
        while not monde.is_done():
            valides = [a for a, ok in enumerate(monde.action_mask()) if ok]
            monde.step(hasard.choice(valides))
            pas += 1
    duree = time.perf_counter() - debut
    return n / duree * 60, pas / n, pas / duree


def mesurer_gym(n=N_PAS_GYM, seed=0):
    """Tours par seconde À TRAVERS Gymnasium : observation et récompense comprises, resets compris.

    C'est la vitesse réelle que verra l'entraînement. Retourne None si gymnasium n'est pas installé.
    """
    try:
        from .env import SurvivalEnv
    except ImportError:
        return None
    env = SurvivalEnv(WorldConfig(max_hp=10**9))  # ne meurt jamais : fin de partie par la limite de tours
    env.reset(seed=seed)
    actions = _actions_au_hasard(seed)
    debut = time.perf_counter()
    for i in range(n):
        _, _, terminated, truncated, _ = env.step(actions[i % len(actions)])
        if terminated or truncated:
            env.reset()
    return n / (time.perf_counter() - debut)


def mesurer_tout(repetitions=3, echelle=1.0):
    """Lance toutes les mesures et retourne un dictionnaire {nom: valeur}.

    Chaque mesure est répétée `repetitions` fois et on garde la MEILLEURE. Pourquoi : un autre
    programme qui s'exécute en même temps peut ralentir une mesure, mais jamais l'accélérer. Le
    meilleur essai est donc le plus proche de la vitesse réelle du code.
    """
    mesurer_pas(n=500)  # échauffement : la toute première exécution est plus lente (caches, imports)

    resets = max(mesurer_resets(_combien(N_RESETS, echelle)) for _ in range(repetitions))
    pas = max(mesurer_pas(_combien(N_PAS, echelle)) for _ in range(repetitions))
    # max() sur des tuples compare d'abord le premier élément : on garde l'essai le plus rapide.
    parties = max(mesurer_parties(_combien(N_PARTIES, echelle)) for _ in range(repetitions))

    mesures = {
        "resets_par_s": resets,
        "pas_par_s": pas,
        "pas_politique_par_s": parties[2],
        "parties_par_min": parties[0],
        "longueur_moyenne_partie": parties[1],
    }
    essais_gym = [mesurer_gym(_combien(N_PAS_GYM, echelle)) for _ in range(repetitions)]
    if essais_gym[0] is not None:
        mesures["pas_gym_par_s"] = max(essais_gym)
    return {nom: round(valeur, 1) for nom, valeur in mesures.items()}


# ---------------------------------------------------------------------------- comparaison
def comparer(actuel, reference, tolerance=0.30):
    """Liste des mesures de vitesse nettement plus lentes que la référence.

    Retourne [(nom, valeur actuelle, valeur de référence), ...], vide si tout va bien.
    - `tolerance` = 0.30 : on accepte jusqu'à 30 % plus lent (le bruit normal d'un PC) ;
    - aller plus vite n'est jamais un problème ;
    - une mesure absente d'un des deux côtés est ignorée (ex. gymnasium non installé).
    """
    regressions = []
    for nom in METRIQUES_DE_VITESSE:
        if nom in actuel and nom in reference:
            if actuel[nom] < reference[nom] * (1 - tolerance):
                regressions.append((nom, actuel[nom], reference[nom]))
    return regressions


def sauvegarder(mesures, chemin):
    """Écrit la référence dans un fichier JSON (avec la machine qui l'a produite)."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = {
        "python": platform.python_version(),
        "plateforme": platform.platform(),
        "mesures": mesures,
    }
    chemin.write_text(json.dumps(contenu, indent=2), encoding="utf-8")


def charger(chemin):
    return json.loads(Path(chemin).read_text(encoding="utf-8"))["mesures"]


def formater(mesures, reference=None):
    """Tableau lisible. Avec une référence, ajoute l'écart en pourcentage."""
    unites = {
        "resets_par_s": "cartes/s",
        "pas_par_s": "tours/s (moteur seul)",
        "pas_politique_par_s": "tours/s (parties complètes, joueur aléatoire)",
        "pas_gym_par_s": "tours/s (via Gymnasium)",
        "parties_par_min": "parties/min (joueur aléatoire)",
        "longueur_moyenne_partie": "tours par partie en moyenne",
    }
    lignes = []
    for nom, valeur in mesures.items():
        ligne = f"{nom:26s} {valeur:>12,.1f}  {unites.get(nom, '')}"
        if reference and nom in reference and reference[nom]:
            ecart = (valeur / reference[nom] - 1) * 100
            ligne += f"   ({ecart:+.0f} % vs référence)"
        lignes.append(ligne)
    return "\n".join(lignes)


# ---------------------------------------------------------------------------- ligne de commande
def main(argv=None):
    parseur = argparse.ArgumentParser(description="Mesure la vitesse du moteur.")
    parseur.add_argument("--repetitions", type=int, default=3, help="essais par mesure (défaut 3)")
    parseur.add_argument("--echelle", type=float, default=1.0, help="réduit la durée (0.1 = 10 fois plus court)")
    parseur.add_argument("--tolerance", type=float, default=0.30, help="ralentissement toléré (défaut 0.30)")
    parseur.add_argument("--baseline", default=str(REFERENCE_PAR_DEFAUT), help="fichier de référence")
    mode = parseur.add_mutually_exclusive_group()
    mode.add_argument("--save", action="store_true", help="enregistre les mesures comme référence")
    mode.add_argument("--check", action="store_true", help="compare à la référence (code 1 si plus lent)")
    args = parseur.parse_args(argv)

    reference = None
    if args.check:
        if not Path(args.baseline).exists():
            print(f"Pas de référence dans {args.baseline} : lance d'abord avec --save.")
            return 2
        reference = charger(args.baseline)

    mesures = mesurer_tout(args.repetitions, args.echelle)
    print(formater(mesures, reference))

    if args.save:
        sauvegarder(mesures, args.baseline)
        print(f"\nRéférence enregistrée dans {args.baseline}")
    if args.check:
        regressions = comparer(mesures, reference, args.tolerance)
        if regressions:
            print(f"\nRALENTISSEMENT de plus de {args.tolerance:.0%} :")
            for nom, actuel, ref in regressions:
                print(f"  {nom}: {actuel:,.1f} au lieu de {ref:,.1f}")
            return 1
        print("\nOK : aucun ralentissement notable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())