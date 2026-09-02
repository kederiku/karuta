FROM python:3.12-slim AS base

# PATH pointe vers l'environnement d'uv dès cette étape : le doc 09 §3 ne le posait
# que sur l'étage de production, si bien qu'uvicorn était introuvable en dev.
# UV_PYTHON_DOWNLOADS interdit à uv de télécharger un second interpréteur alors que
# l'image en fournit déjà un, ce que le .python-version copié plus bas déclencherait.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# build-essential et libpq-dev couvrent les dépendances sans roue précompilée ;
# curl sert à la sonde de santé du service api.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

FROM base AS deps

# Seuls les deux manifestes : cette couche n'est reconstruite que si les dépendances
# changent, et non à chaque modification du code.
COPY backend/api/pyproject.toml backend/api/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM deps AS dev

# L'outillage de développement s'installe avant la copie du code, pour qu'éditer un
# fichier ne réinstalle pas Ruff, Mypy et pre-commit.
RUN uv sync --frozen --no-install-project

# Le code précède l'installation du projet, contrairement à l'ordre du doc 09 §3 :
# uv.lock déclare karuta en source éditable, et hatchling déduit la distribution des
# fichiers réellement présents. Sans src/, il produit une roue vide — la construction
# reste verte et l'erreur n'apparaît qu'au démarrage, en « No module named karuta ».
COPY backend/api/ .
RUN uv sync --frozen

CMD ["uvicorn", "karuta.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]
