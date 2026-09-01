"""Point d'entrée ASGI de l'API Karuta."""

import os

from fastapi import FastAPI

from karuta.interfaces.api.v1.public import health

API_V1_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    """Construit l'application FastAPI.

    Le schéma OpenAPI décrit l'intégralité de la surface de l'API, routes
    d'administration et d'ingestion comprises : il n'est pas exposé en production, pas
    plus que la documentation interactive qui le consomme.

    Returns:
        L'application prête à être servie.
    """
    # TODO(KAR-11): lire ENVIRONMENT depuis le modèle Settings (pydantic-settings, doc 03 §6).
    is_production = os.environ.get("ENVIRONMENT", "development") == "production"

    app = FastAPI(
        title="Karuta API",
        version="1.0.0",
        redirect_slashes=False,
        docs_url=None if is_production else f"{API_V1_PREFIX}/docs",
        redoc_url=None,
        openapi_url=None if is_production else f"{API_V1_PREFIX}/openapi.json",
    )
    app.include_router(health.router, prefix=API_V1_PREFIX)
    return app


app = create_app()
