"""Middlewares HTTP de l'API (doc 03 §3.2).

Ce module porte aujourd'hui la corrélation des requêtes ; CORS et la limitation de débit y
rejoindront ``RequestContextMiddleware``.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING

import structlog
from starlette.datastructures import MutableHeaders

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send
    from structlog.typing import FilteringBoundLogger

REQUEST_ID_HEADER = "X-Request-ID"

# La valeur vient du client sur une API publique et atterrit telle quelle dans le journal : un
# retour à la ligne y fabriquerait une fausse entrée, et une valeur longue gonflerait chaque
# ligne de la requête. Le jeu de caractères couvre les identifiants qu'émettent les répartiteurs
# de charge et les traceurs ; la borne laisse passer un UUID et un identifiant de trace W3C.
_MAX_REQUEST_ID_LENGTH = 64
_REQUEST_ID_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{_MAX_REQUEST_ID_LENGTH}}}\Z")

_LOGGER: FilteringBoundLogger = structlog.get_logger("karuta.access")


def current_request_id() -> str | None:
    """Retourne le request_id de la requête en cours, ou ``None`` hors requête.

    Destinée aux réponses d'erreur RFC 7807, qui doivent porter le request_id (doc 05 §2) sans
    dépendre du middleware qui l'a lié.

    Returns:
        L'identifiant de corrélation courant, ou ``None`` hors du traitement d'une requête.
    """
    value = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None


def _rejection_reason(value: str) -> str | None:
    """Dit pourquoi une valeur entrante est refusée, ou ``None`` si elle est acceptable."""
    if not value:
        return "empty"
    if len(value) > _MAX_REQUEST_ID_LENGTH:
        return "too_long"
    if _REQUEST_ID_PATTERN.fullmatch(value) is None:
        return "invalid_characters"
    return None


def _level_for(status_code: int) -> int:
    """Donne le niveau de la ligne d'accès à partir du statut de la réponse."""
    if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return logging.ERROR
    if status_code >= HTTPStatus.BAD_REQUEST:
        return logging.WARNING
    return logging.INFO


class RequestContextMiddleware:
    """Lie un identifiant de corrélation à chaque requête et journalise son issue.

    Le middleware lit ``X-Request-ID``, ou en génère un, le lie au contexte structlog et le
    renvoie dans la réponse (doc 05 §1). Tout évènement émis pendant la requête le porte alors
    sans que l'appelant ait à le transmettre (doc 09 §7).

    Le contexte est purgé **à l'entrée** et non à la sortie : la trace qu'uvicorn journalise
    lorsqu'une application ASGI lève est émise après le retour du middleware, dans le même
    contexte, et reste ainsi corrélée à la requête fautive.

    Il est écrit en ASGI pur, et non sur ``BaseHTTPMiddleware`` : il doit voir le statut réel de
    toute réponse, y compris celles que le routeur produit sans passer par une route.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Traite une requête HTTP en la corrélant, et laisse passer le reste inchangé.

        Args:
            scope: Portée ASGI de la connexion.
            receive: Canal de réception des évènements ASGI.
            send: Canal d'émission des évènements ASGI.
        """
        # Le cycle de vie de l'application traverse aussi la pile : purger le contexte ici
        # effacerait celui qu'un démarrage aurait lié.
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        received = _read_request_id_header(scope)
        rejection = None if received is None else _rejection_reason(received)
        request_id = received if received is not None and rejection is None else str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        if rejection is not None:
            # La valeur refusée n'est pas journalisée : c'est précisément elle qui pourrait
            # porter une injection de ligne.
            _LOGGER.warning(
                "request_id_rejected",
                reason=rejection,
                received_length=len(received or ""),
            )

        # Valeur de repli : si l'application lève avant d'avoir commencé sa réponse, c'est
        # le statut que le serveur renverra.
        status_code = int(HTTPStatus.INTERNAL_SERVER_ERROR)
        started_at = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            # Émise dans tous les cas, y compris quand l'application lève : l'exception
            # poursuit alors sa route, la ligne d'accès n'en avale aucune.
            _LOGGER.log(
                _level_for(status_code),
                "http_request",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )


def _read_request_id_header(scope: Scope) -> str | None:
    """Lit l'en-tête de corrélation dans la portée ASGI, sans construire de requête."""
    wanted = REQUEST_ID_HEADER.lower().encode("latin-1")
    # La portée ASGI est typée en Any par Starlette ; l'annotation restitue le contrat que la
    # spécification ASGI garantit : une suite de couples d'octets.
    headers: Iterable[tuple[bytes, bytes]] = scope["headers"]
    for name, value in headers:
        if name.lower() == wanted:
            return value.decode("latin-1")
    return None
