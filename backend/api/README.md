# Karuta — API

Service FastAPI de Karuta : catalogue, offres et historique des prix.

## Prérequis

- Python 3.12 — la version exacte est fixée par `.python-version`.
- `uv`, qui installe l'interpréteur et les dépendances.

## Installation

```bash
uv sync
```

`uv.lock` est versionné : `uv sync --frozen` réinstalle un environnement identique.

## Démarrage

```bash
uv run uvicorn karuta.main:app --reload
```

| URL                                         | Contenu                                     |
| :------------------------------------------ | :------------------------------------------ |
| `http://localhost:8000/api/v1/health`       | Sonde de liveness                           |
| `http://localhost:8000/api/v1/docs`         | Documentation interactive                   |
| `http://localhost:8000/api/v1/openapi.json` | Schéma OpenAPI, source du client TypeScript |

La documentation et le schéma sont désactivés lorsque `ENVIRONMENT=production`.

### Avec Docker Compose

L'API seule ne suffit pas dès qu'une dépendance entre en jeu. La stack complète —
PostgreSQL, Redis, MinIO, l'API en rechargement à chaud, le worker et le scheduler —
se lance depuis la racine du dépôt, après avoir copié `.env.example` vers `.env` :

```bash
cp .env.example .env
docker compose -f docker/compose/docker-compose.yml up -d --build
```

Le code de ce dossier est monté dans le conteneur : une modification est rechargée sans
reconstruction. En revanche, un changement de `uv.lock` impose de renouveler
l'environnement virtuel du conteneur, qui vit dans un volume :

```bash
docker compose -f docker/compose/docker-compose.yml up -d --build --renew-anon-volumes
```

`docker compose … down` conserve les données ; seul `down -v` les détruit — et détruire
le volume `pgdata` est le seul moyen de rejouer `docker/postgres/init.sql`, que
PostgreSQL n'exécute que sur une grappe vide.

pgAdmin est disponible sur `http://localhost:5050` en ajoutant `--profile tools`,
avec `dev@karuta.example.com` / `admin`.

Depuis la racine du dépôt, `make dev` fait la même chose en une commande, et `make down`
arrête la stack. La liste des cibles est dans le README racine.

## Qualité du code

Ruff (lint et format) et Mypy (typage strict) sont configurés dans `pyproject.toml`,
d'après les configurations prescrites par les docs 10 §2 et 20 §22. Depuis ce dossier :

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
```

La CI exécute les mêmes commandes, `ruff format` en mode `--check` (doc 09 §4). Une règle
ne se désactive jamais pour faire passer du code : c'est le code qui est corrigé.

### Hooks pre-commit

Les hooks sont décrits par `.pre-commit-config.yaml`, **à la racine du dépôt** : ils
couvrent Ruff, Gitleaks et Mypy. À installer une fois par clone, depuis n'importe où dans
le dépôt :

```bash
uv run --directory backend/api pre-commit install
```

Pour rejouer tous les hooks sur tout le dépôt sans committer :

```bash
uv run --directory backend/api pre-commit run --all-files
```

Le détour par `uv run --directory` est nécessaire : `pre-commit` est installé dans
l'environnement de ce service, alors que sa configuration vit à la racine.

## Organisation

Architecture hexagonale : les dépendances ne pointent jamais vers l'extérieur.

| Chemin                       | Contenu                                                         |
| :--------------------------- | :-------------------------------------------------------------- |
| `src/karuta/domain/`         | Cœur métier — n'importe ni SQLAlchemy, ni FastAPI, ni Pydantic. |
| `src/karuta/application/`    | Cas d'usage et orchestration.                                   |
| `src/karuta/infrastructure/` | Implémentations techniques : base, cache, stockage, tâches.     |
| `src/karuta/interfaces/`     | Routers FastAPI, schémas Pydantic, commandes.                   |
| `src/karuta/workers/`        | Tâches TaskIQ.                                                  |
| `migrations/`                | Migrations Alembic.                                             |
| `tests/`                     | `unit/`, `integration/`, `e2e/`, `factories/`.                  |
