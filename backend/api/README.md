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

| URL | Contenu |
| :-- | :-- |
| `http://localhost:8000/api/v1/health` | Sonde de liveness |
| `http://localhost:8000/api/v1/docs` | Documentation interactive |
| `http://localhost:8000/api/v1/openapi.json` | Schéma OpenAPI, source du client TypeScript |

La documentation et le schéma sont désactivés lorsque `ENVIRONMENT=production`.

Le lancement via Docker Compose et le point d'entrée unique `make dev` arrivent avec
KAR-6 et KAR-7.

## Organisation

Architecture hexagonale : les dépendances ne pointent jamais vers l'extérieur.

| Chemin | Contenu |
| :-- | :-- |
| `src/karuta/domain/` | Cœur métier — n'importe ni SQLAlchemy, ni FastAPI, ni Pydantic. |
| `src/karuta/application/` | Cas d'usage et orchestration. |
| `src/karuta/infrastructure/` | Implémentations techniques : base, cache, stockage, tâches. |
| `src/karuta/interfaces/` | Routers FastAPI, schémas Pydantic, commandes. |
| `src/karuta/workers/` | Tâches TaskIQ. |
| `migrations/` | Migrations Alembic. |
| `tests/` | `unit/`, `integration/`, `e2e/`, `factories/`. |
