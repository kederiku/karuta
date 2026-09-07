"""Configuration du journal structuré du processus (doc 09 §7).

Un seul appel, ``configure_logging``, sert tous les points d'entrée : l'API, le worker TaskIQ et
les scripts. Le module vit à la racine du paquet, à côté de ``config.py``, et non dans une
couche : il n'implémente aucun port et ne parle à aucun système externe, il amorce le processus
avant que les couches n'existent (doc 03 §3.1).

Il remplace les gestionnaires du journaliste racine : un test qui reposerait sur ``caplog`` après
un appel ne verrait plus rien. Les tests de ce dépôt lisent le flux passé en paramètre.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

from karuta.config import Environment

if TYPE_CHECKING:
    from typing import TextIO

    from structlog.typing import EventDict, Processor, WrappedLogger

    from karuta.config import Settings

# Le doc 05 §10 nomme quatre champs ; la correspondance se fait par sous-chaîne pour attraper
# « postgres_password » ou « x_api_key » sans énumérer les variantes. « authorization » complète
# la liste : c'est l'en-tête qui transporte le jeton.
_SENSITIVE_KEY_MARKERS = ("password", "token", "secret", "api_key", "authorization")

MASK = "***"

# uvicorn porte ses propres gestionnaires et ne propage pas : laissés tels quels, ses journaux
# sortiraient en texte brut sur un second flux, et sa ligne d'accès doublerait celle du
# middleware sans porter ni request_id ni duration_ms.
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def mask_sensitive_values(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Remplace par un masque la valeur de toute clé au nom sensible (doc 05 §10).

    Le masquage porte sur le **nom de la clé**, à toute profondeur : un secret interpolé dans
    une chaîne sous une clé anodine — une URL de connexion, par exemple — reste visible. Il
    complète la protection de ``SecretStr``, qui ne couvre que la configuration.

    Args:
        _logger: Journaliste sous-jacent, inutilisé.
        _method_name: Méthode appelée, inutilisée.
        event_dict: Évènement à masquer, modifié sur place.

    Returns:
        L'évènement dont les valeurs sensibles sont masquées.
    """
    return _mask_mapping(event_dict)


def _mask_mapping(mapping: EventDict) -> EventDict:
    for key, value in mapping.items():
        mapping[key] = MASK if _is_sensitive(key) else _mask_value(value)
    return mapping


def _is_sensitive(key: object) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS)


# Le contenu d'un évènement est arbitraire : structlog le type lui-même en Any (doc 10 §2,
# interopérabilité avec une bibliothèque).
def _mask_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: MASK if _is_sensitive(key) else _mask_value(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_value(item) for item in value)
    return value


def render_unserialisable(value: object) -> str:
    """Rend par son type un objet que JSON ne sait pas sérialiser.

    Le repli de structlog appelle ``repr`` : un objet portant un attribut sensible y sortirait
    en clair, hors de portée du masquage, qui ne voit que les noms de clés (doc 05 §10).

    Args:
        value: Objet refusé par le sérialiseur.

    Returns:
        Le nom de la classe entre chevrons.
    """
    return f"<{type(value).__name__}>"


def _render_processors(environment: Environment) -> list[Processor]:
    """Termine la chaîne : console lisible en développement, JSON ailleurs (doc 09 §7).

    Args:
        environment: Environnement d'exécution du processus.

    Returns:
        Les processeurs de sortie, ``remove_processors_meta`` en tête comme l'exige
        ``ProcessorFormatter``.
    """
    head: list[Processor] = [structlog.stdlib.ProcessorFormatter.remove_processors_meta]
    if environment is Environment.DEVELOPMENT:
        # ConsoleRenderer met lui-même les traces en forme ; les formater en amont lui
        # retirerait sa mise en page.
        return [*head, structlog.dev.ConsoleRenderer()]
    return [
        *head,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(default=render_unserialisable),
    ]


def _rewire_uvicorn_loggers() -> None:
    """Fait passer les journaux d'uvicorn par la chaîne du processus."""
    for name in _UVICORN_LOGGERS:
        server_logger = logging.getLogger(name)
        server_logger.handlers = []
        server_logger.propagate = True
    # Le journal d'accès du serveur n'émet qu'en INFO : relever son seuil le tait sans masquer
    # un avertissement réel. C'est le middleware qui journalise les requêtes, avec le
    # request_id et la durée qu'uvicorn ne connaît pas.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def configure_logging(settings: Settings, *, stream: TextIO | None = None) -> None:
    """Configure structlog et la bibliothèque standard pour tout le processus.

    Rejouable : chaque appel remplace la configuration précédente au lieu de s'y ajouter.

    Args:
        settings: Configuration retenue ; ``environment`` choisit le rendu, ``log_level`` le
            seuil.
        stream: Flux de sortie. Par défaut ``sys.stdout``, résolu à l'appel et non à l'import —
            sous pytest, le flux est remplacé après le chargement des modules, et un
            gestionnaire construit trop tôt écrirait à côté.
    """
    level = logging.getLevelNamesMapping()[settings.log_level]

    # Une seule chaîne pour les deux origines : les évènements structlog la traversent avant
    # « wrap_for_formatter », les enregistrements de la bibliothèque standard y entrent par
    # « foreign_pre_chain ». Sans ce doublement, les seconds sortiraient sans horodatage, sans
    # niveau et sans request_id.
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        # Dernier avant le rendu : le masquage doit voir l'évènement complet, contexte compris.
        mask_sensitive_values,
    ]

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        # Le cache fige la chaîne au premier appel : un second « configure_logging », que les
        # tests provoquent, resterait alors sans effet.
        cache_logger_on_first_use=False,
    )

    handler = logging.StreamHandler(sys.stdout if stream is None else stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=_render_processors(settings.environment),
        )
    )

    root = logging.getLogger()
    # Remplacement et non ajout : un second appel doublerait sinon chaque ligne.
    root.handlers = [handler]
    root.setLevel(level)
    _rewire_uvicorn_loggers()
