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

### Prérequis

- **Docker** et **Docker Compose** — toute la stack de développement tourne en
  conteneurs.
- **Node 24** et **pnpm 11**. `pnpm` ne s'installe pas à la main : `corepack enable`
  suffit, corepack résolvant la version depuis le champ `packageManager` du
  `package.json` racine, qui en est la source de vérité.
- **Python 3.12** et **uv** — `uv` installe lui-même l'interpréteur. Les outils de
  qualité du backend s'exécutent sur le poste, hors conteneur.
- **make** — le point d'entrée unique du dépôt.

Pour tester plus tard le multi-tenant par sous-domaine, ajouter à `/etc/hosts` :

```
127.0.0.1 karuta.local pokemon.karuta.local magic.karuta.local yugioh.karuta.local
```

### Lancer la stack

```bash
corepack enable
pnpm install
make dev
```

`make dev` copie `.env.example` vers `.env` s'il manque, puis démarre PostgreSQL, Redis,
MinIO, l'API en rechargement à chaud, le worker et le scheduler. La stack est prête quand
`http://localhost:8000/api/v1/health` répond `{"status": "ok"}`.

| Service                  | URL                     |
| :----------------------- | :---------------------- |
| API                      | `http://localhost:8000` |
| PostgreSQL               | `localhost:5432`        |
| Redis                    | `localhost:6379`        |
| MinIO (API / console)    | `localhost:9000`/`9001` |
| pgAdmin (profil `tools`) | `http://localhost:5050` |

pgAdmin ne fait pas partie du démarrage par défaut :

```bash
docker compose -f docker/compose/docker-compose.yml --profile tools up -d pgadmin
```

### Les cibles

| Cible                            | Effet                                                    |
| :------------------------------- | :------------------------------------------------------- |
| `make` ou `make help`            | Liste les cibles disponibles.                            |
| `make dev`                       | Lance toute la stack.                                    |
| `make dev-api`                   | Lance l'infrastructure et l'API seules.                  |
| `make down`                      | Arrête la stack en conservant les données.               |
| `make logs`                      | Suit les journaux de l'API et du worker.                 |
| `make lint`                      | Ruff, Mypy, ESLint et TypeScript — ce que vérifie la CI. |
| `make format`                    | Reformate le code Python et JavaScript.                  |
| `make test`                      | Exécute les suites de tests.                             |
| `make migrate`, `make migration` | Migrations Alembic — à partir de KAR-14.                 |
| `make seed`                      | Jeu de données de démonstration — à partir de KAR-24.    |
| `make api-client`                | Régénère le client d'API — à partir de KAR-89.           |
| `make crawl`                     | Lance un spider — à partir de KAR-68.                    |

Les quatre dernières cibles existent déjà mais s'arrêtent sur un message tant que leur
prérequis n'est pas livré. `make test` exécute la suite Python ; son volet JavaScript
reste vide tant qu'aucune application n'a de tests.

`make lint` et `make test` tournent sur le poste et non dans les conteneurs — ils
exécutent exactement ce que lance la CI et n'exigent pas que la stack soit démarrée.

## Configuration

`.env` n'est jamais versionné ; `.env.example` en donne le modèle et décrit une exécution
sur le poste. Il n'y a rien à y modifier pour démarrer : le fichier Compose surcharge les
hôtes par les noms de services du réseau Docker.

`docker compose … down` conserve les données. Seul `down -v` les détruit — et détruire le
volume `pgdata` est le seul moyen de rejouer `docker/postgres/init.sql`, que PostgreSQL
n'exécute que sur une grappe vide.

## Contribuer

`main` est protégée : pas de push direct, pull request obligatoire, CI verte requise.

Une branche par ticket, nommée `<type>/KAR-<id>-<description-courte>` — par exemple
`feat/KAR-23-matching-pipeline`. Les types sont ceux des commits.

Les messages de commit suivent Conventional Commits, avec deux listes fermées :

```
<type>(<scope>): <description à l'impératif, minuscule, sans point final>

[corps optionnel]

[pied optionnel : Refs KAR-12, Refs ADR-0022, BREAKING CHANGE]
```

| Champ | Valeurs admises                                                   |
| :---- | :---------------------------------------------------------------- |
| Type  | `feat` `fix` `refactor` `docs` `test` `chore` `perf`              |
| Scope | `api` `scraping` `frontend` `backoffice` `ui` `db` `infra` `docs` |

Le scope est obligatoire et désigne la zone du dépôt touchée. Un commit qui applique une
décision d'architecture porte le scope de cette zone et cite la décision en pied,
`Refs ADR-00NN`, à côté du `Refs KAR-N`.

commitlint vérifie ce format à deux endroits : un hook `commit-msg` en local, et le job
`commit-lint` en CI. Ce qu'il ne sait pas vérifier reste à la revue — que la description soit
à l'impératif, et qu'elle ne porte pas de majuscule superflue en milieu de phrase, un nom
propre comme `Orval` ou `FastAPI` devant rester possible.

Les pull requests sont fusionnées par commit de fusion, jamais par squash : ce sont les commits
eux-mêmes, déjà vérifiés, qui arrivent sur `main`.

Le reste — modèle de pull request, taille cible, Definition of Done — vit dans le document 10
de l'espace Notion Karuta, seule source de vérité (ADR-0026).
