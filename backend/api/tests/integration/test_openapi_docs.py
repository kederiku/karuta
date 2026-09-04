import pytest
from fastapi.testclient import TestClient

from karuta.config import Environment, Settings
from karuta.main import create_app

FAKE_VALUE = "valeur-factice-a-ne-pas-divulguer"


def build_settings(environment: Environment) -> Settings:
    return Settings(
        environment=environment,
        secret_key=FAKE_VALUE,
        postgres_host="localhost",
        postgres_db="karuta_test",
        postgres_user="test",
        postgres_password=FAKE_VALUE,
        s3_access_key=FAKE_VALUE,
        s3_secret_key=FAKE_VALUE,
        ingest_hmac_secret=FAKE_VALUE,
    )


@pytest.mark.parametrize("environment", [Environment.DEVELOPMENT, Environment.STAGING])
def test_openapi_documentation_outside_production_is_served(environment: Environment) -> None:
    with TestClient(create_app(build_settings(environment))) as client:
        assert client.get("/api/v1/docs").status_code == 200
        assert client.get("/api/v1/openapi.json").status_code == 200


def test_openapi_documentation_in_production_is_not_exposed() -> None:
    with TestClient(create_app(build_settings(Environment.PRODUCTION))) as client:
        assert client.get("/api/v1/docs").status_code == 404
        assert client.get("/api/v1/openapi.json").status_code == 404


def test_application_title_comes_from_the_configured_product_name() -> None:
    settings = build_settings(Environment.DEVELOPMENT).model_copy(
        update={"product_name": "Cartothèque"}
    )

    assert create_app(settings).title == "Cartothèque API"
