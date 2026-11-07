# Workflow Git

## Branches principales

- `main` : version stable. Aucun push direct.
- `dev` : branche d'intÃ©gration.
- `feature/M0-nom` : travail du jalon M0.
- `feature/M1-nom` : travail du jalon M1.
- etc.

## DÃ©velopper un ticket

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

CrÃ©er ensuite une Pull Request :

```text
feature/M0-nom -> dev
```

La PR doit mentionner le ticket :

```text
Closes #123
```

## IntÃ©gration

Les branches de fonctionnalitÃ© sont fusionnÃ©es dans `dev` par Pull Request.

Quand `dev` est suffisamment stable et validÃ©e :

```text
dev -> main
```

Cette PR est la seule maniÃ¨re normale d'intÃ©grer du code dans `main`.

## Interdictions

- Ne jamais pousser directement sur `main`.
- Ne jamais fusionner une branche feature directement dans `main`.
- Ne jamais utiliser `main` comme branche de dÃ©veloppement.
- Ne pas contourner les vÃ©rifications CI.