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

## Configuration

Toute la configuration passe par `src/karuta/config.py` : une classe `Settings`
(pydantic-settings) qui type les variables du doc 03 §6, les valide **au démarrage** et refuse
de démarrer si l'une des variables requises manque. Le message nomme alors les variables
fautives, sans jamais afficher de valeur.

Sont requises, sans valeur par défaut : `ENVIRONMENT`, `SECRET_KEY`, `POSTGRES_HOST`,
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` et
`INGEST_HMAC_SECRET`. Les autres reprennent la valeur de développement du doc 03 §6, qui n'est
pas sensible.

D'où viennent les valeurs :

| Contexte                            | Source                                                                                                                                                         |
| :---------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Poste (`uv run …`, `make test-api`) | Le `.env` de la racine du dépôt. Son chemin est résolu depuis l'emplacement du module, pas depuis le répertoire courant ; `make test-api` le crée s'il manque. |
| Conteneur                           | Les variables fournies par `env_file` et `environment` du fichier Compose — aucun `.env` n'est copié dans l'image.                                             |
| CI                                  | Le bloc `env:` de l'étape « Tests » de `ci-backend.yml`, en valeurs factices : aucun secret réel n'entre en CI (doc 09 §6).                                    |

Les secrets sont typés `SecretStr` : ils n'apparaissent ni dans `repr(settings)`, ni dans un
journal. Les variables `NEXT_PUBLIC_*` du `.env` sont consommées par les applications Next.js et
volontairement absentes de `Settings`.

La configuration s'obtient par `get_settings()` et s'injecte par `Depends(get_settings)` ; elle
n'est jamais importée comme singleton global depuis le domaine.

Les quatre variables de marque — `PRODUCT_NAME`, `PUBLIC_DOMAIN`, `BOT_USER_AGENT` et
`CONTACT_EMAIL` — externalisent ce qui sort vers l'extérieur (Q14, doc 14). « Karuta » reste un
nom de code interne : le paquet Python, la base de développement, les services Docker et le
préfixe `KAR-XX` ne sont pas concernés.

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

Les hooks sont décrits par `.pre-commit-config.yaml`, **à la racine du dépôt**. Avant chaque
commit : Ruff, Gitleaks, Mypy et ESLint. Sur le message de commit : commitlint. À installer une
fois par clone, depuis n'importe où dans le dépôt :

```bash
uv run --directory backend/api pre-commit install
```

La commande installe les deux types de hooks sans drapeau. **Un clone antérieur au hook
`commit-msg` doit la rejouer une fois** : `.git/hooks/` n'est pas versionné.

Pour rejouer tous les hooks sur tout le dépôt sans committer :

```bash
uv run --directory backend/api pre-commit run --all-files
```

Cette commande n'exerce pas commitlint, qui ne tourne qu'au stade `commit-msg` : le format des
messages se vérifie par `bash scripts/check-commit-format.sh`, inclus dans `make lint`.

Le détour par `uv run --directory` est nécessaire : `pre-commit` est installé dans
l'environnement de ce service, alors que sa configuration vit à la racine.

## Tests

Pytest, avec `httpx` pour le client de test de FastAPI. Depuis ce dossier :

```bash
uv run pytest
```

La suite importe `karuta.main`, donc construit `Settings` : elle exige une configuration
complète. Sur un clone neuf, lancer d'abord `make test-api` depuis la racine, qui crée le `.env`
s'il manque — `uv run pytest` seul échouerait à la collecte.

Le seuil de couverture global du backend, 75 % (doc 10 §4), n'est pas dans
`pyproject.toml` : il est porté par la ligne de commande, celle de la cible `make test-api`
et celle de la CI. Pour rejouer exactement ce que vérifie la CI, depuis la racine du dépôt :

```bash
make test-api
```

Les tests vivent dans `tests/`, répartis en `unit/`, `integration/`, `e2e/` et `factories/`
(doc 10 §4) ; les fixtures partagées sont dans `tests/conftest.py`.

## Organisation

Architecture hexagonale : les dépendances ne pointent jamais vers l'extérieur.

| Chemin                       | Contenu                                                         |
| :--------------------------- | :-------------------------------------------------------------- |
| `src/karuta/domain/`         | Cœur métier — n'importe ni SQLAlchemy, ni FastAPI, ni Pydantic. |
| `src/karuta/application/`    | Cas d'usage et orchestration.                                   |
| `src/karuta/infrastructure/` | Implémentations techniques : base, cache, stockage, tâches.     |
| `src/karuta/interfaces/`     | Routers FastAPI, schémas Pydantic, commandes.                   |
| `src/karuta/workers/`        | Tâches TaskIQ.                                                  |
| `src/karuta/config.py`       | Configuration typée, validée au démarrage.                      |
| `migrations/`                | Migrations Alembic.                                             |
| `tests/`                     | `unit/`, `integration/`, `e2e/`, `factories/`.                  |
