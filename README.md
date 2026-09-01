# Karuta

Karuta est une plateforme web de comparaison de prix pour les cartes à
collectionner (TCG) et les produits scellés associés.

« Karuta » est le nom de code interne du projet, pas une marque.

## Les trois briques

- **Application publique** (Next.js) — landing page et comparateur avec filtres
  avancés, multilingue et multi-tenant par licence.
- **Back-office** (Next.js) — gestion du catalogue et des boutiques, et surtout
  du *matching* entre les données brutes scrapées et les entités du catalogue.
- **Chaîne de données** (Scrapy + FastAPI + PostgreSQL + TaskIQ) — collecte,
  staging, réconciliation, historisation des prix.

## Organisation du dépôt

| Chemin | Contenu |
| :-- | :-- |
| `backend/api/` | Service FastAPI (domaine, application, infrastructure, interfaces, workers). |
| `backend/scraping/` | Projet Scrapy : spiders, pipelines, extracteurs. |
| `frontend/` | Application publique Next.js. |
| `backoffice/` | Application d'administration Next.js. |
| `packages/` | Paquets partagés entre les deux applications : UI, configurations, types. |
| `docker/` | Dockerfiles et fichiers Docker Compose. |
| `docs/` | Décisions d'architecture (`docs/adr/`) et procédures d'exploitation (`docs/runbooks/`). |
| `scripts/` | Scripts transverses (seed, génération du client d'API, partitions). |

## Documentation

- Spécifications produit et techniques : dossier Drive privé « Karuta » (accès
  sur demande).
- Décisions d'architecture : [`docs/adr/`](docs/adr/).

## Démarrage

Aucun outil n'est encore configuré à ce stade du projet. Le point d'entrée
unique (`make dev`) et la procédure d'installation arrivent avec KAR-7.

## Configuration

Copier `.env.example` vers `.env` et renseigner les valeurs locales. Le fichier
`.env` n'est jamais versionné.
