import io
import json
import logging
from collections.abc import Callable, Iterator

import pytest
import structlog

from karuta.config import Environment, LogLevel, Settings
from karuta.logging_config import MASK, configure_logging

# Toutes les valeurs sensibles du jeu de test partagent ce littéral, ce qui permet de le chercher
# dans une sortie de journal pour vérifier qu'aucun secret n'en sort.
FAKE_VALUE = "valeur-factice-a-ne-pas-divulguer"

# Les valeurs sensibles sont fabriquées plutôt qu'écrites en clair : Ruff refuse un littéral
# affecté à un nom de champ sensible, et la règle vaut aussi pour un jeu de test.
SENSITIVE_FIELDS = ("password", "access_token", "postgres_password", "s3_secret_key", "API_KEY")
SENSITIVE_VALUES = {name: f"secret-{index}" for index, name in enumerate(SENSITIVE_FIELDS)}
NESTED_MARKER = "temoin-imbrique"
LISTED_MARKER = "temoin-en-liste"
TUPLED_MARKER = "temoin-en-tuple"
HELD_MARKER = "temoin-porte-par-un-objet"

Configure = Callable[..., io.StringIO]


def build_settings(
    environment: Environment = Environment.PRODUCTION,
    log_level: LogLevel = LogLevel.INFO,
) -> Settings:
    return Settings(
        environment=environment,
        log_level=log_level,
        secret_key=FAKE_VALUE,
        postgres_host="localhost",
        postgres_db="karuta_test",
        postgres_user="test",
        postgres_password=FAKE_VALUE,
        s3_access_key=FAKE_VALUE,
        s3_secret_key=FAKE_VALUE,
        ingest_hmac_secret=FAKE_VALUE,
    )


@pytest.fixture
def configure() -> Iterator[Configure]:
    # configure_logging remplace les gestionnaires du journaliste racine et la configuration
    # globale de structlog : sans restauration, l'ordre des tests deviendrait significatif.
    root = logging.getLogger()
    previous_handlers = root.handlers[:]
    previous_level = root.level

    def _configure(
        environment: Environment = Environment.PRODUCTION,
        log_level: LogLevel = LogLevel.INFO,
    ) -> io.StringIO:
        stream = io.StringIO()
        configure_logging(build_settings(environment, log_level), stream=stream)
        return stream

    yield _configure

    structlog.reset_defaults()
    root.handlers = previous_handlers
    root.setLevel(previous_level)
    structlog.contextvars.clear_contextvars()


@pytest.mark.parametrize("environment", [Environment.PRODUCTION, Environment.STAGING])
def test_configure_logging_outside_development_renders_one_json_line_per_event(
    configure: Configure, environment: Environment
) -> None:
    stream = configure(environment)

    structlog.get_logger("essai").info("evenement_de_test", cle="valeur")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "evenement_de_test"
    assert record["level"] == "info"
    assert record["logger"] == "essai"
    assert record["cle"] == "valeur"
    assert record["timestamp"].endswith("Z")


def test_configure_logging_in_development_renders_a_readable_line(configure: Configure) -> None:
    stream = configure(Environment.DEVELOPMENT)

    structlog.get_logger("essai").info("evenement_de_test")

    rendered = stream.getvalue()
    assert "evenement_de_test" in rendered
    with pytest.raises(json.JSONDecodeError):
        json.loads(rendered)


def test_configure_logging_applies_the_configured_threshold(configure: Configure) -> None:
    stream = configure(log_level=LogLevel.WARNING)
    logger = structlog.get_logger("essai")

    logger.info("sous_le_seuil")
    logger.warning("au_dessus_du_seuil")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "au_dessus_du_seuil"


def test_configure_logging_replayed_does_not_duplicate_lines(configure: Configure) -> None:
    configure()
    stream = configure()

    structlog.get_logger("essai").info("evenement_de_test")

    assert len(stream.getvalue().splitlines()) == 1


def test_standard_library_records_are_rendered_by_the_same_chain(configure: Configure) -> None:
    stream = configure()

    logging.getLogger("sqlalchemy.engine").warning("SELECT 1")
    logging.getLogger("uvicorn.error").info("Application startup complete.")
    logging.getLogger().error("racine")

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(lines) == 3
    assert [record["logger"] for record in lines] == ["sqlalchemy.engine", "uvicorn.error", "root"]
    assert [record["level"] for record in lines] == ["warning", "info", "error"]
    assert all(record["timestamp"].endswith("Z") for record in lines)


def test_standard_library_records_carry_the_bound_context(configure: Configure) -> None:
    stream = configure()

    structlog.contextvars.bind_contextvars(request_id="req-1")
    logging.getLogger("uvicorn.error").error("Application startup failed.")

    assert json.loads(stream.getvalue().strip())["request_id"] == "req-1"


def test_uvicorn_access_log_is_silenced(configure: Configure) -> None:
    # Le middleware journalise chaque requête avec le request_id et la durée : la ligne
    # d'uvicorn ferait doublon sans les porter.
    stream = configure()

    logging.getLogger("uvicorn.access").info('GET /api/v1/health HTTP/1.1" 200')

    assert stream.getvalue() == ""
    assert logging.getLogger("uvicorn.access").level >= logging.WARNING
    assert logging.getLogger("uvicorn").handlers == []


def test_sensitive_keys_are_masked_at_every_depth(configure: Configure) -> None:
    stream = configure()

    structlog.get_logger("essai").info(
        "evenement_sensible",
        **SENSITIVE_VALUES,
        # La clé entière vérifie que le masquage ne suppose pas des noms de clés textuels :
        # rien n'impose à un évènement de n'en porter que.
        nested={"niveau": {"refresh_token": NESTED_MARKER}, 7: "anodin"},
        listed=[{"api_key": LISTED_MARKER}],
        tupled=({"api_key": TUPLED_MARKER},),
    )

    rendered = stream.getvalue()
    expected = [*SENSITIVE_VALUES.values(), NESTED_MARKER, LISTED_MARKER, TUPLED_MARKER]
    assert not any(secret in rendered for secret in expected)
    record = json.loads(rendered)
    assert [record[name] for name in SENSITIVE_FIELDS] == [MASK] * len(SENSITIVE_FIELDS)
    assert record["nested"]["niveau"]["refresh_token"] == MASK
    assert record["nested"]["7"] == "anodin"
    assert record["listed"][0]["api_key"] == MASK
    assert record["tupled"][0]["api_key"] == MASK


def test_unserialisable_values_are_rendered_by_their_type(configure: Configure) -> None:
    # Le repli de structlog appelle repr : un objet portant un attribut sensible y sortirait en
    # clair, hors de portée du masquage, qui ne voit que les noms de clés.
    class Credentials:
        def __init__(self) -> None:
            self.password = HELD_MARKER

        def __repr__(self) -> str:
            return f"Credentials(password={self.password!r})"

    stream = configure()

    structlog.get_logger("essai").info("evenement_sensible", holder=Credentials())

    rendered = stream.getvalue()
    assert HELD_MARKER not in rendered
    assert json.loads(rendered)["holder"] == "<Credentials>"


def test_logging_the_settings_object_reveals_no_secret(configure: Configure) -> None:
    stream = configure()

    structlog.get_logger("essai").info("configuration", settings=build_settings())

    assert FAKE_VALUE not in stream.getvalue()
