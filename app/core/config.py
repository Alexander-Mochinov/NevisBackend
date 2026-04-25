"""Application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    app_env: str = Field(default="local", validation_alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+asyncpg://nevis:nevis@localhost:5432/nevis",
        validation_alias="DATABASE_URL",
    )
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias="EMBEDDING_MODEL_NAME",
    )
    embedding_provider: Literal["fake", "sentence_transformers"] = Field(
        default="fake",
        validation_alias="EMBEDDING_PROVIDER",
    )
    embedding_dimension: int = Field(
        default=384,
        ge=1,
        validation_alias="EMBEDDING_DIMENSION",
    )
    enable_summary: bool = Field(default=False, validation_alias="ENABLE_SUMMARY")
    search_result_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias="SEARCH_RESULT_LIMIT",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
