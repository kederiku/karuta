"""Configuration d'exécution de l'API, lue depuis l'environnement et validée au démarrage.

L'application refuse de démarrer si une variable requise manque : mieux vaut un arrêt immédiat
et nommé qu'une valeur par défaut silencieuse découverte en production (doc 03 §6).
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file(module_path: Path) -> Path | None:
    """Cherche le .env de la racine du dépôt en remontant depuis un module.

    Le fichier vit à la racine alors que les commandes du projet s'exécutent depuis
    backend/api : résolu depuis le répertoire courant, il ne serait jamais trouvé. La racine se
    reconnaît à son .env.example, versionné. Remonter d'un nombre fixe de niveaux serait plus
    court mais dépasserait la racine du système de fichiers dans l'image, où /app vaut
    backend/api.

    Args:
        module_path: Fichier depuis lequel remonter.

    Returns:
        Le chemin du .env attendu, ou ``None`` hors du dépôt — en conteneur notamment, où le
        .dockerignore écarte ces fichiers et où les valeurs arrivent par l'environnement.
    """
    for directory in module_path.resolve().parents:
        if (directory / ".env.example").is_file():
            return directory / ".env"
    return None


_ENV_FILE = _find_env_file(Path(__file__))


class Environment(StrEnum):
    """Environnement d'exécution du processus (doc 03 §6)."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    """Configuration absente ou invalide, relevée au démarrage.

    Le message nomme les variables d'environnement fautives, telles qu'on les écrit dans un
    fichier .env, et non les champs du modèle.
    """


class Settings(BaseSettings):
    """Configuration complète de l'API.

    Les champs sans valeur par défaut sont requis : secrets, identifiants de connexion et
    environnement d'exécution. Les autres reprennent les valeurs de développement du doc 03 §6,
    qui ne sont pas sensibles.

    S'obtient par ``get_settings`` et s'injecte par ``Depends`` ; le domaine ne l'importe jamais
    (règle de dépendance, doc 03 §3.1).
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        # Le même fichier porte les variables NEXT_PUBLIC_* du frontend, que ce modèle ne
        # couvre pas : sans cette tolérance, pydantic-settings les rejetterait comme inconnues.
        extra="ignore",
        frozen=True,
    )

    # Général
    environment: Environment
    log_level: str = "INFO"
    secret_key: SecretStr

    # Base de données
    postgres_host: str
    postgres_port: int = Field(default=5432, gt=0, lt=65536)
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    database_pool_size: int = Field(default=20, gt=0)
    database_max_overflow: int = Field(default=10, ge=0)

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    taskiq_broker_url: str = "redis://localhost:6379/1"

    # Stockage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_bucket: str = "karuta-media"
    s3_public_url: str = "http://localhost:9000/karuta-media"

    # Auth
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, gt=0)
    jwt_refresh_token_expire_days: int = Field(default=7, gt=0)

    # Ingestion
    ingest_hmac_secret: SecretStr
    ingest_max_batch_size: int = Field(default=500, gt=0)

    # Matching — seuils sur 100, repli du seuil par boutique (Q11, doc 14).
    match_auto_threshold: int = Field(default=100, ge=0, le=100)
    match_review_threshold: int = Field(default=70, ge=0, le=100)

    # Marque (Q14) : tout ce qui sort vers l'extérieur. « Karuta » reste un nom de code interne,
    # donc le paquet Python, la base de développement et les services Docker n'en relèvent pas.
    # Le domaine d'exemple est réservé par la RFC 2606 : le domaine public n'est pas encore
    # choisi, Q14 étant reportée. L'agent utilisateur du bot (doc 06 §2.4) est une variable à
    # part entière, que KAR-59 composera depuis les trois autres au lieu de la lire telle quelle.
    product_name: str = "Karuta"
    public_domain: str = "karuta.local"
    bot_user_agent: str = (
        "KarutaBot/1.0 (+https://karuta.example.com/bot; contact@karuta.example.com)"
    )
    contact_email: str = "contact@karuta.example.com"


def _describe(error: ValidationError) -> str:
    missing = sorted(
        {_variable_name(item["loc"]) for item in error.errors() if item["type"] == "missing"}
    )
    invalid = sorted(
        {_variable_name(item["loc"]) for item in error.errors() if item["type"] != "missing"}
    )

    parts = []
    if missing:
        parts.append(f"variables manquantes : {', '.join(missing)}")
    if invalid:
        parts.append(f"variables invalides : {', '.join(invalid)}")
    return f"Configuration d'environnement inutilisable — {' ; '.join(parts)}."


def _variable_name(location: tuple[int | str, ...]) -> str:
    return str(location[0]).upper() if location else "?"


@lru_cache
def get_settings() -> Settings:
    """Retourne la configuration du processus, lue et validée une seule fois.

    S'utilise telle quelle comme dépendance FastAPI : ``Depends(get_settings)``.

    Returns:
        La configuration validée.

    Raises:
        ConfigurationError: Si une variable requise manque ou si une valeur est refusée. Le
            message nomme les variables fautives ; il ne porte aucune valeur, les secrets ne
            devant jamais atteindre un journal (doc 09 §6).
    """
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigurationError(_describe(error)) from error
