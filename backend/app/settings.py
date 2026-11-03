"""Configuración global de la aplicación cargada desde variables de entorno."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de configuración del sistema Pampero."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Entorno
    environment: str = "development"
    debug: bool = False

    # Base de datos
    database_url: SecretStr = Field(
        default=SecretStr(
            "postgresql+asyncpg://pampero_app:pampero_app_secret@localhost:5432/pampero"
        ),
        description="URL asíncrona para la API HTTP",
    )
    database_sync_url: SecretStr = Field(
        default=SecretStr(
            "postgresql+psycopg://pampero_app:pampero_app_secret@localhost:5432/pampero"
        ),
        description="URL síncrona para Celery y scripts",
    )
    database_url_owner: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://postgres:postgres@localhost:5432/pampero"),
        description="URL con privilegios de propietario para migraciones Alembic",
    )

    # Redis y Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Seguridad y autenticación
    admin_token: SecretStr = Field(
        default=SecretStr("pampero-dev-admin-token"),
        description="Token secreto para endpoints de administración X-Admin-Token",
    )
    secret_key: SecretStr = Field(
        default=SecretStr("pampero-insecure-dev-secret-key-change-me"),
        description="Clave secreta general",
    )
    api_key_pepper: SecretStr = Field(
        default=SecretStr("pampero-default-pepper-secret"),
        description="Pepper para hashing HMAC-SHA256 de API keys de usuarios",
    )

    # LLM y Embeddings
    llm_provider: Literal["fake", "litellm"] = "fake"
    llm_model: str = "gemini/gemini-2.5-flash"
    llm_fallback_model: str = "openai/gpt-4.1-mini"
    embedding_provider: Literal["fake", "litellm"] = "fake"
    embedding_model: str = "gemini/gemini-embedding-001"
    embedding_dim: int = 768
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # Ingesta y RAG
    parser: Literal["pypdf", "docling"] = "pypdf"
    rag_min_similarity: float = 0.30
    storage_path: str = "./data/uploads"

    # Observabilidad
    otel_service_name: str = "pampero-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_traces_sampler: str = "parentbased_always_on"

    # Puertos
    web_port: int = 5173
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Retorna la instancia cacheada de la configuración del sistema."""
    return Settings()
