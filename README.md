# AI Survivor

Une IA de survie qui apprend en jouant. Elle observe son environnement, évalue ses besoins, choisit un objectif, agit, vérifie le résultat et change de stratégie quand la situation évolue. Le but final est un agent **entièrement autonome**, sans stratégie toute faite.

> **Statut : fondations.** Le dépôt met en place l'outillage (M0) et le moteur de simulation sans fenêtre (M1). Le suivi se fait dans les [jalons](../../milestones) et les [tickets](../../issues).

## Principe

- **Un cerveau générique, un monde extensible.** Chaque mécanique (faim, météo, véhicules, électricité…) ajoute des observations, des actions, des besoins ou des événements. Le cerveau ne change pas, il réapprend à chaque palier.
- **L'objectif vient des besoins.** À chaque tour, chaque besoin (santé, sécurité, arme, puis faim, soif, énergie) reçoit une urgence. L'objectif courant est le besoin le plus urgent : il bascule tout seul quand la situation change.
- **Les compétences sont indépendantes.** Fuir, soigner, fouiller… chacune est une compétence ajoutable en un fichier. Un script expert sert d'abord de référence, puis la compétence est apprise seulement si le script est insuffisant.
- **L'aléatoire est reproductible.** Chaque partie est générée avec une seed, pour apprendre des principes et pas des positions.
- **L'IA s'entraîne en jouant** sur des milliers de parties, est évaluée sur des scénarios fixes sans exploration, puis réentraînée par paliers en rejouant les anciens scénarios pour limiter l'oubli.

## Stack technique

Décisions du ticket « 0.4 — Stack technique et décisions » :

| Domaine | Choix |
|---|---|
| Langage | Python 3.11 |
| Apprentissage | PyTorch |
| Interface agent/monde | Gymnasium (`reset` / `step`) |
| Algorithme de départ | PPO avec masquage des actions impossibles (Stable-Baselines3 et sb3-contrib) |
| Performance | NumPy, puis Numba ; environnements parallèles |
| Suivi et configuration | TensorBoard, YAML, checkpoints PyTorch |
| Affichage | pygame, séparé du moteur |

Après M4, passage à Rust à envisager si le moteur devient le goulot d'étranglement.

## Feuille de route

| Jalon | Contenu |
|---|---|
| M0 | Fondations DevOps |
| M1 | Environnement sans fenêtre |
| M2 | Besoins, objectifs et lecture de situation |
| M3 | Compétences et politique apprise |
| M4 | Entraînement, évaluation et paliers |
| M5 | Perception partielle et ouïe |
| M6 | Monde |
| M7 | Survie et récompenses |
| M8 | Inventaire et ressources |
| M9 | Construction et fortification |
| M10 | Véhicules |
| M11 | Agriculture et élevage |
| M12 | Exploration |
| M13 | Artisanat et production |
| M14 | Combat et soins |
| M15 | Faune et nature |
| M16 | Météo et catastrophes |
| M17 | Économie et fouille |
| M18 | Événements du monde |
| M19 | Personnage et progression |
| M20 | Électricité |

Chaque jalon contient ses tickets, numérotés `M.n` (par exemple « 2.3 — Objectif = besoin le plus urgent »).

## Contribuer

Le workflow complet est décrit dans [`BRANCHING.md`](BRANCHING.md).

- `main` : version stable, jamais de push direct.
- `dev` : branche d'intégration.
- `feature/Mx-nom` : une branche par ticket, créée depuis `dev`, fusionnée par Pull Request vers `dev`.
- Chaque PR mentionne son ticket (`Closes #N`) et doit passer la CI (`ruff check .` et `pytest -q`).

Les labels indiquent le domaine : `ia`, `monde`, `survie`, `devops`, `tests`.
