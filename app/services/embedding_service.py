"""Embedding providers for document chunks."""

import hashlib
import importlib
from typing import Any, Final, Protocol

from app.core.config import Settings

EXPECTED_EMBEDDING_DIMENSION: Final = 384


class EmbeddingProvider(Protocol):
    """Interface for query and document embedding providers."""

    dimension: int

    def encode_query(self, text: str) -> list[float]:
        """Encode a single search query."""

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode document or chunk texts."""


class FakeEmbeddingProvider:
    """Deterministic local embedding provider for tests and development."""

    def __init__(self, *, dimension: int) -> None:
        self.dimension = dimension

    def encode_query(self, text: str) -> list[float]:
        return _validate_vector_dimension(self._embed(text), expected_dimension=self.dimension)

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            _validate_vector_dimension(self._embed(text), expected_dimension=self.dimension)
            for text in texts
        ]

    def _embed(self, text: str) -> list[float]:
        normalized_text = " ".join(text.split())
        if not normalized_text:
            return [0.0] * self.dimension

        vector: list[float] = []
        for index in range(self.dimension):
            digest = hashlib.blake2b(
                f"{normalized_text}\0{index}".encode(),
                digest_size=8,
            ).digest()
            integer = int.from_bytes(digest, byteorder="big", signed=False)
            vector.append((integer / ((1 << 64) - 1)) * 2.0 - 1.0)
        return vector


class SentenceTransformerEmbeddingProvider:
    """Production local embedding provider backed by sentence-transformers."""

    def __init__(self, *, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self.dimension = dimension
        self._model: Any | None = None

    def encode_query(self, text: str) -> list[float]:
        return self.encode_documents([text])[0]

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._load_model()
        encoded = model.encode(texts, normalize_embeddings=True)
        vectors = [self._to_float_list(vector) for vector in encoded]
        return [
            _validate_vector_dimension(vector, expected_dimension=self.dimension)
            for vector in vectors
        ]

    def _load_model(self) -> Any:
        if self._model is None:
            module = importlib.import_module("sentence_transformers")
            model_class = getattr(module, "SentenceTransformer")
            self._model = model_class(self._model_name)
        return self._model

    @staticmethod
    def _to_float_list(vector: Any) -> list[float]:
        if hasattr(vector, "tolist"):
            return [float(value) for value in vector.tolist()]
        return [float(value) for value in vector]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Create the configured embedding provider."""
    _validate_configured_dimension(settings.embedding_dimension)

    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(dimension=settings.embedding_dimension)

    return SentenceTransformerEmbeddingProvider(
        model_name=settings.embedding_model_name,
        dimension=settings.embedding_dimension,
    )


def _validate_configured_dimension(dimension: int) -> None:
    if dimension != EXPECTED_EMBEDDING_DIMENSION:
        raise ValueError(
            "Unsupported EMBEDDING_DIMENSION: "
            f"expected {EXPECTED_EMBEDDING_DIMENSION} because document_chunks.embedding "
            f"uses vector({EXPECTED_EMBEDDING_DIMENSION}); got {dimension}. "
            "Changing embedding dimension requires a database migration."
        )


def _validate_vector_dimension(
    vector: list[float],
    *,
    expected_dimension: int,
) -> list[float]:
    if len(vector) != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dimension}, got {len(vector)}"
        )
    return vector
