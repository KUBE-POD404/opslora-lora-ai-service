from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_env_files() -> None:
    explicit = os.getenv("ENV_FILE")
    if explicit:
        load_dotenv(explicit, override=False)
        return
    env = os.getenv("ENVIRONMENT", "development")
    for candidate in (f".env.{env}", ".env"):
        if Path(candidate).exists():
            load_dotenv(candidate, override=False)


def _secret(name: str, default: str | None = None, *, required: bool = False) -> str:
    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        value = Path(file_name).read_text(encoding="utf-8").strip()
    else:
        value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"{name} is not set")
    return value or ""


_load_env_files()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = Field(default="opslora-lora-ai-service", validation_alias="SERVICE_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    api_prefix: str = Field(default="/api/v1", validation_alias="API_PREFIX")

    database_url: str = Field(default="sqlite:///./lora_ai_local.db", validation_alias="DATABASE_URL")
    database_pool_size: int = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")
    database_pool_recycle_seconds: int = Field(default=1800, validation_alias="DATABASE_POOL_RECYCLE_SECONDS")
    database_pool_pre_ping: bool = Field(default=True, validation_alias="DATABASE_POOL_PRE_PING")

    primary_ai_provider: str = Field(default="ollama", validation_alias="PRIMARY_AI_PROVIDER")
    enable_azure_foundry_fallback: bool = Field(default=True, validation_alias="ENABLE_AZURE_FOUNDRY_FALLBACK")

    hermes_base_url: str = Field(default="http://127.0.0.1:11434", validation_alias="HERMES_BASE_URL")
    hermes_model: str = Field(default="smollm2:135m", validation_alias="HERMES_MODEL")
    hermes_timeout_seconds: int = Field(default=20, validation_alias="HERMES_TIMEOUT_SECONDS")

    azure_ai_foundry_endpoint: str = Field(default="", validation_alias="AZURE_AI_FOUNDRY_ENDPOINT")
    azure_ai_foundry_deployment: str = Field(default="", validation_alias="AZURE_AI_FOUNDRY_DEPLOYMENT")
    azure_ai_foundry_timeout_seconds: int = Field(default=30, validation_alias="AZURE_AI_FOUNDRY_TIMEOUT_SECONDS")

    vector_url: str = Field(default="http://qdrant:6333", validation_alias="VECTOR_URL")

    @property
    def hermes_api_key(self) -> str:
        return _secret("HERMES_API_KEY")

    @property
    def azure_ai_foundry_api_key(self) -> str:
        return _secret("AZURE_AI_FOUNDRY_API_KEY")

    @property
    def vector_api_key(self) -> str:
        return _secret("VECTOR_API_KEY")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
