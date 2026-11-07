
#requires -Version 5.1
<#
  Mise en place DevOps de Natcraftt/ai-survivor

  À lancer depuis la racine du dépôt, après :
      gh auth login

  Simulation :
      $env:DRY_RUN = '1'
      .\setup-devops.ps1

  Exécution réelle :
      $env:DRY_RUN = '0'
      .\setup-devops.ps1

  Dépôt par défaut :
      Natcraftt/ai-survivor

  Personnaliser le dépôt :
      $env:REPO = 'Natcraftt/ai-survivor'

  Le script :
    - crée ou retrouve les jalons M0 à M20 ;
    - crée les tickets manquants ;
    - rattache les tickets existants aux jalons ;
    - ajoute les labels ;
    - génère les workflows GitHub Actions ;
    - génère les modèles de PR et d'issues.

  IMPORTANT :
    - aucun push n'est effectué ;
    - aucun commit n'est effectué ;
    - aucune fusion n'est effectuée ;
    - aucune branche n'est supprimée ;
    - aucun ancien jalon n'est supprimé ;
    - aucune modification directe de main n'est effectuée.
#>

$ErrorActionPreference = 'Stop'

$DryRun = $env:DRY_RUN -eq '1'
$Repo = if ($env:REPO) { $env:REPO } else { 'Natcraftt/ai-survivor' }

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Dash = [string][char]0x2014

# ------------------------------------------------------------
# Vérifications
# ------------------------------------------------------------

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI introuvable. Installe GitHub CLI : https://cli.github.com/"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git introuvable. Installe Git : https://git-scm.com/"
}

$Auth = & gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Tu dois d'abord te connecter avec : gh auth login"
}

$RepoInfo = & gh api "repos/$Repo" --jq '.full_name' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Impossible d'accéder au dépôt $Repo. Vérifie les droits et le nom du dépôt."
}

Write-Host ""
Write-Host "Dépôt : $RepoInfo" -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "MODE SIMULATION : aucune modification GitHub ne sera effectuée." -ForegroundColor Yellow
}
else {
    Write-Host "MODE RÉEL : les jalons, tickets, labels et fichiers seront créés ou modifiés." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# Fonctions GitHub CLI
# ------------------------------------------------------------

function Invoke-Gh {
    $result = & gh @args

    if ($LASTEXITCODE -ne 0) {
        throw "Échec de la commande gh : gh $($args -join ' ')"
    }

    return $result
}

function Get-GhJson {
    param([string]$Path)

    $raw = Invoke-Gh api $Path
    $json = $raw -join "`n"

    if ([string]::IsNullOrWhiteSpace($json)) {
        return $null
    }

    return $json | ConvertFrom-Json
}

function Send-GhJson {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body
    )

    if ($DryRun) {
        Write-Host "SIMULATION : $Method $Path"
        return $null
    }

    $tempFile = [System.IO.Path]::GetTempFileName()

    try {
        $json = $Body | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($tempFile, $json, $Utf8NoBom)

        $result = Invoke-Gh api -X $Method $Path --input $tempFile

        if ($result) {
            return (($result -join "`n") | ConvertFrom-Json)
        }
    }
    finally {
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    }
}

function Write-ProjectFile {
    param(
        [string]$Path,
        [string]$Content
    )

    $FullPath = Join-Path (Get-Location) $Path
    $Directory = Split-Path $FullPath -Parent

    if (-not (Test-Path $Directory)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }

    if ($DryRun) {
        Write-Host "SIMULATION : écriture de $Path"
        return
    }

    [System.IO.File]::WriteAllText($FullPath, $Content, $Utf8NoBom)
    Write-Host "  Écrit : $Path" -ForegroundColor Green
}

# ------------------------------------------------------------
# Jalons M0 à M20
# ------------------------------------------------------------

$Milestones = @'
M0|Fondations DevOps|Repo Python, CI, conventions de branches, tests automatisés et stack technique documentée.
M1|Environnement sans fenêtre|Simulation headless : carte, murs, zombie, arme, medkit, aléatoire seedé et interface Gymnasium reset/step.
M2|Besoins, objectifs et lecture de situation|L'IA perçoit son monde, calcule ses besoins et choisit automatiquement le besoin le plus urgent. Script expert de référence.
M3|Compétences et politique apprise|Registre de compétences extensible, sélection selon les besoins et première politique apprise.
M4|Entraînement, évaluation et paliers|Entraînement parallèle, évaluation sur cas fixes, curriculum, rejeu anti-oubli et checkpoints.
M5|Perception partielle et ouïe|Champ de vision, raycasting, ouïe et carte des zones vues fournie par le jeu.
M6|Monde : bâtiments, loot, bruit, navigation|Bâtiments, portes, conteneurs, bruit et pathfinding A*/Dijkstra pour les zombies.
M7|Survie et récompenses|Faim, soif, fatigue, blessures, infection et récompenses orientées survie.
M8|Inventaire et ressources|Inventaire, durabilité, consommables, coupures, péremption et jour/nuit.
M9|Construction et fortification|Construction modulaire, barricades, mobilier et dégradation.
M10|Véhicules|Conduite, carburant, mécanique et stockage.
M11|Agriculture et élevage|Plantation, saisons, élevage et conservation.
M12|Exploration|Intérieurs, lieux spéciaux, butin et cartographie.
M13|Artisanat et production|Artisanat avancé, métallurgie, ateliers et recyclage.
M14|Combat et soins|Dégâts par partie du corps, mêlée, furtivité et soins.
M15|Faune et nature|Faune, chasse, pêche et évolution de la nature.
M16|Météo et catastrophes|Météo, température, inondations et incendies.
M17|Économie et fouille|Fouille, rareté, troc et marchands.
M18|Événements du monde|Événements dynamiques, radios, traces et convois.
M19|Personnage et progression|Compétences, apprentissage, traits et condition physique.
M20|Électricité|Production, batteries, câblage et appareils.
'@ -split "`r?`n" | Where-Object { $_.Trim() }

Write-Host ""
Write-Host "== Création des jalons" -ForegroundColor Cyan

$ExistingMilestones = @{}
$MilestoneRows = Invoke-Gh api --paginate "repos/$Repo/milestones?state=all&per_page=100" --jq '.[] | [.title, (.number|tostring)] | @tsv'

foreach ($row in $MilestoneRows) {
    if ($row) {
        $parts = $row -split "`t", 2
        $ExistingMilestones[$parts[0]] = [int]$parts[1]
    }
}

$MilestoneNumbers = @{}
$MilestoneTitles = @{}

foreach ($line in $Milestones) {
    $parts = $line -split '\|', 3

    $Id = $parts[0]
    $Name = $parts[1]
    $Description = $parts[2]
    $Title = "$Id $Dash $Name"

    $MilestoneTitles[$Id] = $Title

    if ($ExistingMilestones.ContainsKey($Title)) {
        $MilestoneNumbers[$Id] = $ExistingMilestones[$Title]
        Write-Host "  Existe : $Title"
        continue
    }

    if ($DryRun) {
        Write-Host "  À créer : $Title"
        $MilestoneNumbers[$Id] = 0
        continue
    }

    $Created = Send-GhJson POST "repos/$Repo/milestones" @{
        title = $Title
        description = $Description
        state = 'open'
    }

    $MilestoneNumbers[$Id] = $Created.number
    Write-Host "  Créé : $Title"
}

# ------------------------------------------------------------
# Labels
# ------------------------------------------------------------

Write-Host ""
Write-Host "== Labels" -ForegroundColor Cyan

$Labels = @{
    ia      = '1d76db'
    monde   = '0e8a16'
    survie  = 'b60205'
    devops  = '5319e7'
    tests   = 'fbca04'
    feature = 'a2eeef'
}

foreach ($LabelName in $Labels.Keys) {
    if ($DryRun) {
        Write-Host "  À créer ou actualiser : $LabelName"
    }
    else {
        Invoke-Gh label create $LabelName `
            --repo $Repo `
            --color $Labels[$LabelName] `
            --force | Out-Null

        Write-Host "  OK : $LabelName"
    }
}

# ------------------------------------------------------------
# Plan des tickets
#
# Format :
# Mx|new|Titre|Description|label
# Mx|numéro_issue
# Mx|numéro_issue|Nouveau titre
# ------------------------------------------------------------

$TicketPlan = @'
M0|new|Structure du repo Python|Python 3.11, dossier src/, tests/, pyproject.toml, requirements.txt et README.||devops
M0|new|CI GitHub Actions|Lint et tests automatisés sur les PR vers dev et main.||devops
M0|new|Conventions de branches et protection de main|Branches feature/Mx-nom. Les fonctionnalités passent par dev. main reçoit uniquement une PR depuis dev.||devops
M0|new|Stack technique et décisions|Python 3.11, PyTorch, Gymnasium reset/step, PPO avec masquage des actions impossibles (Stable-Baselines3 et sb3-contrib au début), NumPy puis Numba, environnements parallèles, TensorBoard, YAML, checkpoints PyTorch et pygame séparé du moteur. Après M4, envisager Rust si le moteur devient le goulot d'étranglement.||devops
M0|72
M1|new|Boucle de simulation headless|Tick, état sérialisable et aucune dépendance à une fenêtre. Objectif : pouvoir simuler des milliers de parties rapidement.||ia
M1|new|Carte, murs et collisions|Créer le monde de base, les obstacles et les règles de collision.||monde
M1|new|Zombie : apparition aléatoire et poursuite|Apparition et déplacement basiques des zombies.||monde
M1|new|Armes et medkit|Ramassage, utilisation des armes et effets des kits de soin.||monde
M1|new|Aléatoire seedé à chaque partie|Les apparitions et événements doivent être reproductibles grâce à une seed.||ia
M1|new|Interface Gymnasium reset/step|API standard pour l'entraînement, avec masque des actions impossibles.||ia
M1|new|Benchmark de vitesse du moteur|Mesurer les parties par minute et détecter les régressions.||tests
M2|new|Perception : vecteur d'observation|Définir les informations numériques accessibles à l'agent.||ia
M2|new|Besoins et urgence|Santé, sécurité, arme, puis faim, soif et énergie. L'urgence est recalculée à chaque tour.||ia
M2|new|Objectif = besoin le plus urgent|L'objectif bascule automatiquement quand une urgence augmente.||ia
M2|new|Lecture de situation en clair|Exemple : PV 1, zombie à 3 cases, pas d'arme, objectif : fuir.||ia
M2|new|Script expert de référence|Un script simple qui joue correctement et sert de base de comparaison.||ia
M2|123
M2|73
M3|new|Registre de compétences extensible|Chaque mécanique devient une compétence indépendante : fuir, soigner, fouiller, etc. Ajouter une compétence ne doit pas nécessiter de modifier tout le système.||ia
M3|new|Niveau haut : choix de la compétence|Le niveau haut, codé au départ, choisit la compétence selon l'objectif courant.||ia
M3|new|Récompense issue des besoins|Une urgence qui baisse donne une récompense ; une urgence qui augmente donne une pénalité.||ia
M3|new|Première compétence apprise : fuir|Politique conditionnée par l'objectif et avec masquage des actions impossibles. Comparaison au script expert sur scénarios fixes.||ia
M3|52
M3|53
M3|54
M4|new|Entraînement massif parallèle|Environnements vectorisés et entraînement sur plusieurs cœurs.||ia
M4|new|Évaluation sur scénarios fixes|Évaluation périodique sans exploration pour mesurer les progrès réels.||ia
M4|new|Apprentissage par paliers et rejeu|Réentraîner après chaque mécanique en rejouant les anciens scénarios pour limiter l'oubli.||ia
M4|new|Suivi, configuration et checkpoints|TensorBoard, YAML, checkpoints, statistiques et reprise de l'entraînement.||devops
M4|55
M4|74
M5|56
M5|57|Ouïe et carte des zones vues fournie par le jeu
M6|58
M6|59
M6|60
M6|61
M6|62
M7|63
M7|64
M7|65
M7|66
M8|67
M8|68
M8|69
M8|70
M8|71
M9|75
M9|76
M9|77
M9|78
M10|79
M10|80
M10|81
M10|82
M11|83
M11|84
M11|85
M11|86
M12|87
M12|88
M12|89
M12|90
M13|91
M13|92
M13|93
M13|94
M14|95
M14|96
M14|97
M14|98
M15|99
M15|100
M15|101
M15|102
M16|103
M16|104
M16|105
M16|106
M17|107
M17|108
M17|109
M17|110
M18|111
M18|112
M18|113
M18|114
M19|115
M19|116
M19|117
M19|118
M20|119
M20|120
M20|121
M20|122
'@ -split "`r?`n" | Where-Object { $_.Trim() }

# ------------------------------------------------------------
# Récupération des tickets existants
# ------------------------------------------------------------

Write-Host ""
Write-Host "== Récupération des tickets existants" -ForegroundColor Cyan

$ExistingIssues = @{}

$IssueRows = Invoke-Gh api --paginate "repos/$Repo/issues?state=all&per_page=100" --jq '.[] | select(.pull_request == null) | [.number, .title] | @tsv'

foreach ($row in $IssueRows) {
    if ($row) {
        $parts = $row -split "`t", 2
        $ExistingIssues[[int]$parts[0]] = $parts[1]
    }
}

$ExistingTitles = @{}
foreach ($number in $ExistingIssues.Keys) {
    $ExistingTitles[$ExistingIssues[$number]] = $true
}

# ------------------------------------------------------------
# Création et rattachement des tickets
# ------------------------------------------------------------

Write-Host ""
Write-Host "== Création et rattachement des tickets" -ForegroundColor Cyan

$Counters = @{}

foreach ($line in $TicketPlan) {
    $parts = $line -split '\|', 5

    $MilestoneId = $parts[0]
    $Reference = $parts[1]

    if (-not $Counters.ContainsKey($MilestoneId)) {
        $Counters[$MilestoneId] = 0
    }

    $Counters[$MilestoneId]++
    $TicketPrefix = "$($MilestoneId.Substring(1)).$($Counters[$MilestoneId])"

    if ($Reference -eq 'new') {
        $OriginalTitle = $parts[2]
        $Body = if ($parts.Count -gt 3) { $parts[3] } else { '' }
        $Label = if ($parts.Count -gt 4 -and $parts[4]) { $parts[4] } else { 'feature' }

        $Body = $Body.Replace('\n', "`n")
        $Title = "$TicketPrefix $Dash $OriginalTitle"

        if ($ExistingTitles.ContainsKey($Title)) {
            Write-Host "  Existe déjà : $Title"
            continue
        }

        if ($DryRun) {
            Write-Host "  À créer : $Title"
            continue
        }

        $MilestoneNumber = $MilestoneNumbers[$MilestoneId]

        $CreatedIssue = Send-GhJson POST "repos/$Repo/issues" @{
            title = $Title
            body = $Body
            milestone = $MilestoneNumber
            labels = @($Label)
        }

        Write-Host "  Créé #$($CreatedIssue.number) : $Title"
        $ExistingTitles[$Title] = $true
        continue
    }

    $IssueNumber = [int]$Reference

    if (-not $ExistingIssues.ContainsKey($IssueNumber)) {
        Write-Warning "Issue #$IssueNumber introuvable. Ignorée."
        continue
    }

    $OldTitle = $ExistingIssues[$IssueNumber]
    $OverrideTitle = if ($parts.Count -gt 2 -and $parts[2]) { $parts[2] } else { $null }

    if ($OverrideTitle) {
        $CleanTitle = $OverrideTitle
    }
    else {
        $CleanTitle = $OldTitle -replace '^(?:T)?\d+\.\d+\s+—\s*', ''
    }

    $NewTitle = "$TicketPrefix $Dash $CleanTitle"

    if ($DryRun) {
        Write-Host "  #$IssueNumber -> $NewTitle"
        continue
    }

    Send-GhJson PATCH "repos/$Repo/issues/$IssueNumber" @{
        title = $NewTitle
        milestone = $MilestoneNumbers[$MilestoneId]
    } | Out-Null

    Write-Host "  #$IssueNumber -> $NewTitle"
}

# ------------------------------------------------------------
# GitHub Actions : CI
#
# - PR vers dev : vérification
# - PR vers main : vérification
# - push sur dev : vérification
# - aucun push direct sur main attendu
# ------------------------------------------------------------

Write-Host ""
Write-Host "== Génération des workflows GitHub Actions" -ForegroundColor Cyan

Write-ProjectFile '.github/workflows/ci.yml' @'
name: CI

on:
  pull_request:
    branches:
      - dev
      - main
  push:
    branches:
      - dev

permissions:
  contents: read

jobs:
  ci:
    name: Tests et qualité
    runs-on: ubuntu-latest

    steps:
      - name: Récupération du dépôt
        uses: actions/checkout@v4

      - name: Installation de Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Installation des outils
        run: |
          python -m pip install --upgrade pip
          pip install ruff pytest

      - name: Installation des dépendances du projet
        run: |
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          fi

      - name: Vérification Ruff
        run: ruff check .

      - name: Tests Pytest
        run: |
          if [ -d tests ]; then
            pytest -q
          else
            echo "Aucun dossier tests pour le moment."
          fi
'@

# ------------------------------------------------------------
# GitHub Actions : règles des PR
#
# - feature/* vers dev : autorisé
# - dev vers main : autorisé
# - feature/* vers main : refusé
# - toute autre source vers main : refusée
# ------------------------------------------------------------

Write-ProjectFile '.github/workflows/pr-hygiene.yml' @'
name: PR hygiene

on:
  pull_request:
    types:
      - opened
      - edited
      - synchronize
      - reopened

permissions:
  pull-requests: read
  contents: read

jobs:
  validate:
    name: Vérification des règles de branches
    runs-on: ubuntu-latest

    steps:
      - name: Vérifier la branche source et la destination
        uses: actions/github-script@v7
        with:
          script: |
            const pr = context.payload.pull_request;
            const head = pr.head.ref;
            const base = pr.base.ref;
            const body = pr.body || "";

            if (base === "main" && head !== "dev") {
              core.setFailed(
                "La branche main ne peut recevoir une PR que depuis dev."
              );
              return;
            }

            if (base === "dev" && !head.startsWith("feature/") && head !== "dev") {
              core.setFailed(
                "Une PR vers dev doit provenir d'une branche feature/Mx."
              );
              return;
            }

            if (base === "main" && head === "dev") {
              core.info("PR dev -> main autorisée.");
            }

            if (base === "dev" && head.startsWith("feature/")) {
              core.info("PR feature -> dev autorisée.");
            }

            if (!/(close[sd]?|fix(e[sd])?|resolve[sd]?)\s+#\d+/i.test(body)) {
              core.setFailed(
                "La description de la PR doit contenir Closes #N."
              );
            }
'@

# ------------------------------------------------------------
# Modèle de Pull Request
# ------------------------------------------------------------

Write-ProjectFile '.github/PULL_REQUEST_TEMPLATE.md' @'
## Résumé

Décris ici les changements apportés.

## Ticket associé

Closes #

## Branche

- [ ] Cette PR vient d'une branche `feature/Mx-nom`
- [ ] La destination est `dev`
- [ ] Si cette PR vise `main`, sa source est exclusivement `dev`

## Vérifications

- [ ] Tests ajoutés ou mis à jour
- [ ] `ruff check .` passe
- [ ] `pytest -q` passe
- [ ] Aucun changement non lié au ticket
- [ ] Réévaluation IA sur scénarios fixes si le cerveau ou le monde change
'@

# ------------------------------------------------------------
# Modèle d'issue
# ------------------------------------------------------------

Write-ProjectFile '.github/ISSUE_TEMPLATE/feature.md' @'
---
name: Fonctionnalité
about: Nouvelle mécanique ou amélioration du projet
title: ""
labels: feature
assignees: ""
---

## Objectif

Quel problème cette fonctionnalité doit-elle résoudre ?

## Description

Décris le comportement attendu.

## Éléments concernés

- Observations :
- Actions :
- Besoins :
- Événements :
- Systèmes concernés :

## Critères d'acceptation

- [ ] 
- [ ] 
- [ ] 

## Tests

Comment vérifier que la fonctionnalité fonctionne ?
'@

# ------------------------------------------------------------
# Documentation du workflow Git
# ------------------------------------------------------------

Write-ProjectFile 'BRANCHING.md' @'
# Workflow Git

## Branches principales

- `main` : version stable. Aucun push direct.
- `dev` : branche d'intégration.
- `feature/M0-nom` : travail du jalon M0.
- `feature/M1-nom` : travail du jalon M1.
- etc.

## Développer un ticket

Toujours partir de `dev` :

```bash
git switch dev
git pull origin dev
git switch -c feature/M0-nom
```

Faire le travail, puis publier la branche :

```bash
git add .
git commit -m "feat(M0): description"
git push -u origin feature/M0-nom
```

Créer ensuite une Pull Request :

```text
feature/M0-nom -> dev
```

La PR doit mentionner le ticket :

```text
Closes #123
```

## Intégration

Les branches de fonctionnalité sont fusionnées dans `dev` par Pull Request.

Quand `dev` est suffisamment stable et validée :

```text
dev -> main
```

Cette PR est la seule manière normale d'intégrer du code dans `main`.

## Interdictions

- Ne jamais pousser directement sur `main`.
- Ne jamais fusionner une branche feature directement dans `main`.
- Ne jamais utiliser `main` comme branche de développement.
- Ne pas contourner les vérifications CI.
'@

# ------------------------------------------------------------
# Résumé
# ------------------------------------------------------------

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Configuration terminée." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "Aucune modification distante n'a été effectuée."
    Write-Host "Pour exécuter réellement :"
    Write-Host "  `$env:DRY_RUN = '0'"
    Write-Host "  .\setup-devops.ps1"
}
else {
    Write-Host ""
    Write-Host "Les jalons, tickets, labels et fichiers ont été traités."
    Write-Host ""
    Write-Host "Étapes suivantes :" -ForegroundColor Yellow
    Write-Host "1. Vérifier les jalons et tickets sur GitHub."
    Write-Host "2. Vérifier les fichiers générés dans .github/."
    Write-Host "3. Créer ou vérifier la branche dev."
    Write-Host "4. Créer une branche feature depuis dev."
    Write-Host "5. Committer les fichiers sur cette branche."
    Write-Host "6. Pousser cette branche et ouvrir une PR vers dev."
    Write-Host ""
    Write-Host "Exemple de commandes :" -ForegroundColor Cyan
    Write-Host "  git switch dev"
    Write-Host "  git pull origin dev"
    Write-Host "  git switch -c feature/M0-devops"
    Write-Host "  git add .github BRANCHING.md"
    Write-Host "  git commit -m 'chore: configure DevOps workflow'"
    Write-Host "  git push -u origin feature/M0-devops"
    Write-Host "  gh pr create --base dev --fill"
}

Write-Host ""
Write-Host "RAPPEL : ce script ne pousse jamais sur main." -ForegroundColor Green
