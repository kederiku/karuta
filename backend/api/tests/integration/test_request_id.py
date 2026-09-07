import io
import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from karuta.config import Environment, LogLevel, Settings
from karuta.interfaces.api.middleware import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    current_request_id,
)
from karuta.logging_config import configure_logging
from karuta.main import create_app

FAKE_VALUE = "valeur-factice-a-ne-pas-divulguer"


def build_settings() -> Settings:
    # Rendu JSON : les assertions portent sur des champs nommés, pas sur une mise en forme.
    return Settings(
        environment=Environment.PRODUCTION,
        log_level=LogLevel.INFO,
        secret_key=FAKE_VALUE,
        postgres_host="localhost",
        postgres_db="karuta_test",
        postgres_user="test",
        postgres_password=FAKE_VALUE,
        s3_access_key=FAKE_VALUE,
        s3_secret_key=FAKE_VALUE,
        ingest_hmac_secret=FAKE_VALUE,
    )


def build_app() -> FastAPI:
    app = create_app(build_settings())

    @app.get("/probe")
    async def probe() -> dict[str, str | None]:
        # Aucun request_id n'est passé : c'est le contexte lié par le middleware qui doit le
        # porter jusqu'à la ligne rendue.
        structlog.get_logger("essai").info("sonde")
        return {"seen": current_request_id()}

    @app.get("/typed")
    async def typed(value: int) -> dict[str, int]:
        return {"value": value}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        structlog.contextvars.bind_contextvars(user_id="u-1")
        raise RuntimeError("échec volontaire")

    return app


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    root = logging.getLogger()
    previous_handlers = root.handlers[:]
    previous_level = root.level
    stream = io.StringIO()
    configure_logging(build_settings(), stream=stream)

    yield stream

    structlog.reset_defaults()
    root.handlers = previous_handlers
    root.setLevel(previous_level)
    structlog.contextvars.clear_contextvars()


# Le client HTTP des tests journalise lui aussi, et le pont stdlib le fait passer par la même
# sortie : les assertions ne portent que sur les évènements émis par l'application.
APPLICATION_LOGGERS = ("essai", "karuta.access")


def records(stream: io.StringIO) -> list[dict[str, Any]]:
    lines = (json.loads(line) for line in stream.getvalue().splitlines())
    return [record for record in lines if record["logger"] in APPLICATION_LOGGERS]


def access_lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [record for record in records(stream) if record["event"] == "http_request"]


def test_request_without_the_header_gets_a_generated_identifier(log_stream: io.StringIO) -> None:
    with TestClient(build_app()) as client:
        first = client.get("/probe")
        second = client.get("/probe")

    assert uuid.UUID(first.headers[REQUEST_ID_HEADER])
    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]
    assert [line["request_id"] for line in access_lines(log_stream)] == [
        first.headers[REQUEST_ID_HEADER],
        second.headers[REQUEST_ID_HEADER],
    ]


def test_incoming_header_is_reused_as_is(log_stream: io.StringIO) -> None:
    with TestClient(build_app()) as client:
        response = client.get("/probe", headers={REQUEST_ID_HEADER: "abc-123"})

    assert response.headers[REQUEST_ID_HEADER] == "abc-123"
    assert all(record["request_id"] == "abc-123" for record in records(log_stream))


@pytest.mark.parametrize(
    ("received", "reason"),
    [
        ("", "empty"),
        ("x" * 65, "too_long"),
        ("trace\nGET /faux", "invalid_characters"),
        ("trace\x1b[31m", "invalid_characters"),
    ],
)
def test_malformed_incoming_header_is_rejected_and_replaced(
    log_stream: io.StringIO, received: str, reason: str
) -> None:
    with TestClient(build_app()) as client:
        response = client.get("/probe", headers={REQUEST_ID_HEADER: received})

    assert uuid.UUID(response.headers[REQUEST_ID_HEADER])
    rejections = [
        record for record in records(log_stream) if record["event"] == "request_id_rejected"
    ]
    assert len(rejections) == 1
    assert rejections[0]["reason"] == reason
    assert rejections[0]["level"] == "warning"
    assert rejections[0]["received_length"] == len(received)
    # La valeur refusée n'est jamais journalisée : c'est elle qui pourrait porter l'injection.
    assert received not in log_stream.getvalue() or received == ""


def test_events_emitted_during_a_request_carry_its_identifier(log_stream: io.StringIO) -> None:
    with TestClient(build_app()) as client:
        response = client.get("/probe", headers={REQUEST_ID_HEADER: "abc-123"})

    probe_lines = [record for record in records(log_stream) if record["event"] == "sonde"]
    assert len(probe_lines) == 1
    assert probe_lines[0]["request_id"] == "abc-123"
    # Le contexte est aussi lisible depuis le handler, ce dont KAR-32 aura besoin.
    assert response.json() == {"seen": "abc-123"}


@pytest.mark.asyncio
async def test_identifier_does_not_leak_between_requests(log_stream: io.StringIO) -> None:
    # httpx.ASGITransport exécute chaque requête dans le contexte de l'appelant : contrairement
    # à TestClient, il expose une fuite de contextvars au lieu de la masquer.
    transport = httpx.ASGITransport(app=build_app())
    sent = ["req-a", "req-b", "req-c"]

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for request_id in sent:
            await client.get("/probe", headers={REQUEST_ID_HEADER: request_id})

    assert [record["request_id"] for record in records(log_stream)] == [
        "req-a",
        "req-a",
        "req-b",
        "req-b",
        "req-c",
        "req-c",
    ]


def test_access_line_describes_the_request(log_stream: io.StringIO) -> None:
    with TestClient(build_app()) as client:
        client.get("/api/v1/health")

    lines = access_lines(log_stream)
    assert len(lines) == 1
    assert lines[0]["method"] == "GET"
    assert lines[0]["path"] == "/api/v1/health"
    assert lines[0]["status_code"] == 200
    assert lines[0]["level"] == "info"
    assert isinstance(lines[0]["duration_ms"], float)
    assert lines[0]["duration_ms"] > 0


def test_access_line_of_a_client_error_is_a_warning(log_stream: io.StringIO) -> None:
    with TestClient(build_app()) as client:
        client.get("/inconnu")

    lines = access_lines(log_stream)
    assert len(lines) == 1
    assert lines[0]["status_code"] == 404
    assert lines[0]["level"] == "warning"


def test_a_raising_handler_is_logged_once_then_propagates(log_stream: io.StringIO) -> None:
    with TestClient(build_app(), raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    lines = access_lines(log_stream)
    assert len(lines) == 1
    assert lines[0]["status_code"] == 500
    assert lines[0]["level"] == "error"


def test_the_header_is_returned_on_every_response_the_stack_produces(
    log_stream: io.StringIO,
) -> None:
    # Le 500 de ServerErrorMiddleware fait exception : ce middleware est au-dessus de la pile
    # utilisateur, sa réponse ne traverse pas la nôtre. KAR-32 le fermera depuis le contexte.
    with TestClient(build_app()) as client:
        responses = [
            client.get("/api/v1/health"),
            client.get("/inconnu"),
            client.post("/api/v1/health"),
            client.get("/typed", params={"value": "pas-un-entier"}),
        ]

    assert [response.status_code for response in responses] == [200, 404, 405, 422]
    assert all(REQUEST_ID_HEADER in response.headers for response in responses)


def test_the_correlation_middleware_is_the_outermost_user_middleware() -> None:
    # Starlette insère chaque « add_middleware » en tête de pile : un middleware ajouté après
    # celui-ci — CORS, la limitation de débit — deviendrait le plus externe et court-circuiterait
    # la corrélation. La pile est donc déclarée explicitement dans create_app.
    app = create_app(build_settings())

    # Annoté en object : Starlette type ce champ par un protocole de fabrique, que mypy ne fait
    # pas recouper avec une classe concrète dans un test d'identité.
    outermost: object = app.user_middleware[0].cls

    assert outermost is RequestContextMiddleware


def test_current_request_id_is_none_outside_a_request() -> None:
    structlog.contextvars.clear_contextvars()

    assert current_request_id() is None
