# Karuta

Karuta est une plateforme web de comparaison de prix pour les cartes à
collectionner (TCG) et les produits scellés associés.

« Karuta » est le nom de code interne du projet, pas une marque.

## Les trois briques

- **Application publique** (Next.js) — landing page et comparateur avec filtres
  avancés, multilingue et multi-tenant par licence.
- **Back-office** (Next.js) — gestion du catalogue et des boutiques, et surtout
  du _matching_ entre les données brutes scrapées et les entités du catalogue.
- **Chaîne de données** (Scrapy + FastAPI + PostgreSQL + TaskIQ) — collecte,
  staging, réconciliation, historisation des prix.

## Organisation du dépôt

| Chemin              | Contenu                                                                      |
| :------------------ | :--------------------------------------------------------------------------- |
| `backend/api/`      | Service FastAPI (domaine, application, infrastructure, interfaces, workers). |
| `backend/scraping/` | Projet Scrapy : spiders, pipelines, extracteurs.                             |
| `frontend/`         | Application publique Next.js.                                                |
| `backoffice/`       | Application d'administration Next.js.                                        |
| `packages/`         | Paquets partagés entre les deux applications : UI, configurations, types.    |
| `docker/`           | Dockerfiles et fichiers Docker Compose.                                      |
| `docs/`             | Procédures d'exploitation (`docs/runbooks/`).                                |
| `scripts/`          | Scripts transverses (seed, génération du client d'API, partitions).          |

## Documentation

L'espace Notion « Karuta » est la source de vérité du projet, en lecture comme en
écriture (ADR-0026). On y trouve les spécifications produit et techniques
(documents 00 à 20), les tickets `KAR-XX` de la base « Backlog Karuta » et les
décisions d'architecture, dans le dossier « ADR » (ADR-0027). Accès sur demande.

GitHub n'héberge que le code : dépôt, branches, pull requests et GitHub Actions.

Le dépôt garde sa documentation technique propre : les procédures d'exploitation
dans [`docs/runbooks/`](docs/runbooks/) et un README par service.

## Démarrage

Le workspace pnpm est en place : `pnpm install` à la racine résout les deux
applications et les paquets partagés (Node 24, pnpm 11). Le reste de l'outillage
et le point d'entrée unique (`make dev`) arrivent avec KAR-5 et KAR-7.

## Configuration

Copier `.env.example` vers `.env` et renseigner les valeurs locales. Le fichier
`.env` n'est jamais versionné.
