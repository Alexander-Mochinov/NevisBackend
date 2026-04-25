"""Settings tests."""

from pytest import MonkeyPatch

from app.core.config import Settings


def test_settings_load_safe_defaults(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("ENABLE_SUMMARY", raising=False)
    monkeypatch.delenv("SEARCH_RESULT_LIMIT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_provider == "fake"
    assert settings.embedding_dimension == 384
    assert settings.enable_summary is False
    assert settings.search_result_limit == 10


def test_settings_load_environment_values(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "local-test-model")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "sentence_transformers")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "384")
    monkeypatch.setenv("ENABLE_SUMMARY", "true")
    monkeypatch.setenv("SEARCH_RESULT_LIMIT", "25")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/test"
    assert settings.embedding_model_name == "local-test-model"
    assert settings.embedding_provider == "sentence_transformers"
    assert settings.embedding_dimension == 384
    assert settings.enable_summary is True
    assert settings.search_result_limit == 25
