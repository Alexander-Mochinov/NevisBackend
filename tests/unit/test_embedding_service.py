"""Embedding service tests."""

import sys

import pytest

from app.core.config import Settings
from app.services.embedding_service import (
    FakeEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    create_embedding_provider,
)


def test_fake_embedding_returns_dimension_384() -> None:
    provider = FakeEmbeddingProvider(dimension=384)

    vector = provider.encode_query("address proof")

    assert len(vector) == 384


def test_fake_embedding_is_deterministic() -> None:
    provider = FakeEmbeddingProvider(dimension=384)

    first_vector = provider.encode_query("utility bill")
    second_vector = provider.encode_query("utility bill")

    assert first_vector == second_vector


def test_fake_embedding_empty_text_is_safe() -> None:
    provider = FakeEmbeddingProvider(dimension=384)

    assert provider.encode_query("") == [0.0] * 384


def test_sentence_transformer_provider_does_not_load_model_during_init() -> None:
    sys.modules.pop("sentence_transformers", None)

    provider = SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )

    assert provider.dimension == 384
    assert "sentence_transformers" not in sys.modules


def test_embedding_provider_factory_uses_fake_provider() -> None:
    settings = Settings(
        _env_file=None,
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_DIMENSION=384,
    )

    provider = create_embedding_provider(settings)

    assert isinstance(provider, FakeEmbeddingProvider)


def test_embedding_provider_factory_rejects_dimension_not_matching_db_vector() -> None:
    settings = Settings(
        _env_file=None,
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_DIMENSION=512,
    )

    with pytest.raises(ValueError, match="vector\\(384\\)"):
        create_embedding_provider(settings)
