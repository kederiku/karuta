from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from karuta.config import ConfigurationError, Settings, _find_env_file, get_settings

# Toutes les valeurs sensibles du jeu de test partagent ce littéral, ce qui permet de le
# chercher dans une représentation de l'objet pour vérifier qu'aucun secret n'en sort.
FAKE_VALUE = "valeur-factice-a-ne-pas-divulguer"

REQUIRED_ENV = {
    "ENVIRONMENT": "development",
    "SECRET_KEY": FAKE_VALUE,
    "POSTGRES_HOST": "localhost",
    "POSTGRES_DB": "karuta_test",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": FAKE_VALUE,
    "S3_ACCESS_KEY": FAKE_VALUE,
    "S3_SECRET_KEY": FAKE_VALUE,
    "INGEST_HMAC_SECRET": FAKE_VALUE,
}

ENV_NAMES = [name.upper() for name in Settings.model_fields]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sans neutralisation du .env de la racine, une variable retirée par un test y serait
    # relue et le test passerait pour la mauvaise raison.
    config: dict[str, Any] = Settings.model_config  # type: ignore[assignment]
    monkeypatch.setitem(config, "env_file", None)
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def test_get_settings_when_required_variable_missing_names_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SECRET_KEY")

    with pytest.raises(ConfigurationError) as error:
        get_settings()

    assert "SECRET_KEY" in str(error.value)


def test_get_settings_when_several_variables_missing_names_them_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SECRET_KEY")
    monkeypatch.delenv("POSTGRES_PASSWORD")
    monkeypatch.delenv("INGEST_HMAC_SECRET")

    with pytest.raises(ConfigurationError) as error:
        get_settings()

    message = str(error.value)
    assert "SECRET_KEY" in message
    assert "POSTGRES_PASSWORD" in message
    assert "INGEST_HMAC_SECRET" in message


def test_get_settings_when_environment_is_unknown_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "preproduction")

    with pytest.raises(ConfigurationError) as error:
        get_settings()

    assert "ENVIRONMENT" in str(error.value)


def test_get_settings_when_threshold_is_out_of_bounds_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATCH_AUTO_THRESHOLD", "101")

    with pytest.raises(ConfigurationError) as error:
        get_settings()

    assert "MATCH_AUTO_THRESHOLD" in str(error.value)


def test_get_settings_when_a_variable_is_absent_from_the_error_message_it_is_not_faulty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SECRET_KEY")

    with pytest.raises(ConfigurationError) as error:
        get_settings()

    assert "POSTGRES_HOST" not in str(error.value)


def test_get_settings_reads_values_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("PRODUCT_NAME", "Cartothèque")

    settings = get_settings()

    assert settings.postgres_port == 6543
    assert settings.product_name == "Cartothèque"
    assert settings.secret_key.get_secret_value() == FAKE_VALUE


def test_get_settings_applies_the_documented_defaults() -> None:
    settings = get_settings()

    assert settings.log_level == "INFO"
    assert settings.postgres_port == 5432
    assert settings.match_auto_threshold == 100
    assert settings.match_review_threshold == 70
    assert settings.ingest_max_batch_size == 500


def test_settings_representation_hides_every_secret() -> None:
    settings = get_settings()

    assert FAKE_VALUE not in repr(settings)
    assert FAKE_VALUE not in str(settings)


def test_get_settings_ignores_the_frontend_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXT_PUBLIC_API_URL", "http://localhost:8000")
    monkeypatch.setenv("NEXT_PUBLIC_ROOT_DOMAIN", "karuta.local")

    settings = get_settings()

    assert not hasattr(settings, "next_public_api_url")


def test_get_settings_returns_the_same_instance_on_every_call() -> None:
    assert get_settings() is get_settings()


def test_get_settings_resolves_as_a_fastapi_dependency() -> None:
    # Le critère « injectée via Depends » se vérifie sur le contrat de la dépendance, aucun
    # routeur du projet ne consommant encore la configuration.
    app = FastAPI()

    @app.get("/product-name")
    def read_product_name(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
        return {"product_name": settings.product_name}

    with TestClient(app) as client:
        assert client.get("/product-name").json() == {"product_name": "Karuta"}


def test_find_env_file_returns_the_sibling_of_the_example_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / ".env.example").touch()
    module = root / "backend" / "api" / "src" / "karuta" / "config.py"
    module.parent.mkdir(parents=True)
    module.touch()

    assert _find_env_file(module) == root / ".env"


def test_find_env_file_outside_a_repository_returns_none(tmp_path: Path) -> None:
    # Reproduit l'arborescence de l'image, où /app vaut backend/api et où aucun .env.example
    # n'est copié : la remontée atteint la racine du système de fichiers sans rien trouver.
    module = tmp_path.resolve() / "app" / "src" / "karuta" / "config.py"
    module.parent.mkdir(parents=True)
    module.touch()

    assert _find_env_file(module) is None


def test_find_env_file_locates_the_repository_of_this_checkout() -> None:
    import karuta.config

    found = _find_env_file(Path(karuta.config.__file__))

    assert found is not None
    assert found.name == ".env"
    assert (found.parent / ".env.example").is_file()
