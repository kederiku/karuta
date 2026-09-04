# Le fichier de compose vit dans docker/compose/ alors que les cibles sont lancées depuis la
# racine du dépôt : sans -f, aucune d'elles ne trouverait le projet.
COMPOSE := docker compose -f docker/compose/docker-compose.yml

# Les outils Python tournent sur l'hôte et non dans le conteneur : c'est ce qu'exécutent la CI
# et pre-commit, et cela garde « make lint » utilisable sans stack démarrée, alors que le doc 19
# §6 en fait un préalable à tout commit.
UV_API := uv run --directory backend/api

.DEFAULT_GOAL := help

.PHONY: help dev dev-api down logs migrate migration seed test test-api test-front lint format \
	api-client crawl

help:           ## Liste les cibles disponibles
	@awk -F':.*## ' '/^[a-z][a-z-]*:.*## /{printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev: .env       ## Lance toute la stack de développement
	$(COMPOSE) up -d

dev-api: .env   ## Lance l'infrastructure et l'API seules
	$(COMPOSE) up -d postgres redis minio api worker

down:           ## Arrête la stack en conservant les données
	$(COMPOSE) down

logs:           ## Suit les journaux de l'API et du worker
	$(COMPOSE) logs -f api worker

# Compose lit ../../.env par env_file et refuse de démarrer api, worker et scheduler s'il manque.
# La cible n'a délibérément aucun prérequis : la lier à .env.example écraserait les valeurs
# locales dès que ce dernier serait modifié.
.env:
	cp .env.example .env

migrate:        ## Applique les migrations
	@test -f backend/api/alembic.ini || { echo "make migrate : disponible à partir de KAR-14."; exit 1; }
	$(COMPOSE) exec api alembic upgrade head

migration:      ## Crée une migration : make migration m="ajout table x"
	@test -f backend/api/alembic.ini || { echo "make migration : disponible à partir de KAR-14."; exit 1; }
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

seed:           ## Charge le jeu de données de démonstration
	@test -f scripts/seed.py || { echo "make seed : disponible à partir de KAR-24."; exit 1; }
	$(COMPOSE) exec api python -m scripts.seed

test: test-api test-front  ## Exécute les suites de tests

# Depuis KAR-11, l'import de karuta.main construit Settings, qui refuse de démarrer sans ses
# variables : sur un poste fraîchement cloné, la suite échouerait avant le premier test. La CI
# n'a pas ce prérequis, aucun .env n'y étant versionné — elle les porte au bloc env: de son
# étape « Tests ».
test-api: .env  ## Exécute la suite Python avec la couverture
	$(UV_API) pytest -x --cov=karuta --cov-report=term-missing --cov-fail-under=75

test-front:     ## Exécute les suites JavaScript
	pnpm test

lint:           ## Vérifie le style, le formatage, les types et le format des commits
	$(UV_API) ruff check .
	$(UV_API) ruff format --check .
	$(UV_API) mypy .
	pnpm lint
	pnpm format:check
	pnpm typecheck
# Le job commit-lint exécute ce même script : sans lui ici, une PR pouvait être verte en local
# et rouge en CI, le faux vert que la parité du doc 19 §6 vise à fermer.
	bash scripts/check-commit-format.sh

format:         ## Reformate le code Python et JavaScript
	$(UV_API) ruff format .
	pnpm format

api-client:     ## Régénère le client d'API (Orval)
	@test -f frontend/orval.config.ts || { echo "make api-client : disponible à partir de KAR-89."; exit 1; }
	pnpm --filter frontend generate:api
	pnpm --filter backoffice generate:api

crawl:          ## Lance un spider : make crawl store=cardshop
	@test -f docker/scraping/Dockerfile || { echo "make crawl : disponible à partir de KAR-68."; exit 1; }
	$(COMPOSE) run --rm scraping scrapy crawl $(store)
