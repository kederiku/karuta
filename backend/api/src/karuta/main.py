"""Point d'entrée ASGI de l'API Karuta."""

from fastapi import FastAPI
from starlette.middleware import Middleware

from karuta.config import Environment, Settings, get_settings
from karuta.interfaces.api.middleware import RequestContextMiddleware
from karuta.interfaces.api.v1.public import health
from karuta.logging_config import configure_logging

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
        # La pile est déclarée ici plutôt que montée par « add_middleware » : Starlette insère
        # chaque ajout en tête, si bien qu'un middleware posé plus tard — CORS, la limitation
        # de débit — deviendrait le plus externe et court-circuiterait la corrélation.
        middleware=[Middleware(RequestContextMiddleware)],
    )
    app.include_router(health.router, prefix=API_V1_PREFIX)
    return app


# Le journal est configuré avant la construction de l'application, pour que les messages de
# démarrage sortent déjà au format du processus. L'appel vit ici et non dans « create_app » :
# une application construite dans un test avec une autre configuration n'a pas à reconfigurer
# le journal de tout le processus.
configure_logging(get_settings())
app = create_app()
