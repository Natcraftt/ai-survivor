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


Créer ensuite une Pull Request : `feature/M0-nom -> dev`.

La PR doit mentionner le ticket, par exemple `Closes #123`.

## Intégration

Les branches de fonctionnalité sont fusionnées dans `dev` par Pull Request.

Quand `dev` est suffisamment stable et validée, ouvrir une PR `dev -> main`.
C'est la seule manière normale d'intégrer du code dans `main`.

## Interdictions
- Ne jamais pousser directement sur `main`.
- Ne jamais fusionner une branche feature directement dans `main`.
- Ne jamais utiliser `main` comme branche de développement.
- Ne pas contourner les vérifications CI.
