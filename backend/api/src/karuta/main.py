"""Point d'entrée ASGI de l'API Karuta."""

from fastapi import FastAPI

from karuta.config import Environment, Settings, get_settings
from karuta.interfaces.api.v1.public import health

API_V1_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construit l'application FastAPI.

    Le schéma OpenAPI décrit l'intégralité de la surface de l'API, routes
    d'administration et d'ingestion comprises : il n'est pas exposé en production, pas
    plus que la documentation interactive qui le consomme.

    Le titre vient de la configuration : « Karuta » est un nom de code interne et le nom
    affiché doit pouvoir changer sans toucher au code (Q14, doc 14).

    Args:
        settings: Configuration à servir. Par défaut, celle du processus — un argument
            explicite permet de construire une application dans un autre environnement
            sans passer par les variables du processus. Une route qui déclarera
            ``Depends(get_settings)`` recevra alors la configuration du processus, non
            celle-ci : les deux ne coïncident que par ``app.dependency_overrides``.

    Returns:
        L'application prête à être servie.
    """
    if settings is None:
        settings = get_settings()
    is_production = settings.environment is Environment.PRODUCTION

    app = FastAPI(
        title=f"{settings.product_name} API",
        version="1.0.0",
        redirect_slashes=False,
        docs_url=None if is_production else f"{API_V1_PREFIX}/docs",
        redoc_url=None,
        openapi_url=None if is_production else f"{API_V1_PREFIX}/openapi.json",
    )
    app.include_router(health.router, prefix=API_V1_PREFIX)
    return app


app = create_app()
