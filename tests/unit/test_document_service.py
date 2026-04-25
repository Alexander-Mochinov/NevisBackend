"""Document service tests."""

import uuid
from typing import Any

import pytest

from app.models import Document
from app.schemas.documents import DocumentCreate
from app.services.chunking_service import ChunkingService
from app.services.documents import DocumentService
from app.services.embedding_service import FakeEmbeddingProvider
from app.services.summary_service import SummaryService


class FakeDocumentRepository:
    """Repository double that captures document creation inputs."""

    def __init__(self) -> None:
        self.created_with: dict[str, Any] | None = None
        self.committed = False

    async def client_exists(self, client_id: uuid.UUID) -> bool:
        return True

    async def create_document(
        self,
        *,
        client_id: uuid.UUID,
        title: str,
        content: str,
        summary: str | None,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> Document:
        self.created_with = {
            "client_id": client_id,
            "title": title,
            "content": content,
            "summary": summary,
            "chunks": chunks,
            "embeddings": embeddings,
        }
        return Document(
            id=uuid.uuid4(),
            client_id=client_id,
            title=title,
            content=content,
            summary=summary,
        )

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        raise AssertionError("rollback should not be called")


@pytest.mark.asyncio
async def test_document_service_uses_fake_embeddings_for_chunks() -> None:
    repository = FakeDocumentRepository()
    service = DocumentService(
        repository=repository,  # type: ignore[arg-type]
        chunking_service=ChunkingService(chunk_size=80, overlap_size=20),
        embedding_provider=FakeEmbeddingProvider(dimension=384),
        summary_service=SummaryService(),
    )

    await service.create_document(
        client_id=uuid.uuid4(),
        payload=DocumentCreate(
            title="Utility Bill",
            content=(
                "The client uploaded a utility bill. "
                "The file proves the current address for onboarding."
            ),
        ),
    )

    assert repository.created_with is not None
    embeddings = repository.created_with["embeddings"]
    chunks = repository.created_with["chunks"]
    assert len(embeddings) == len(chunks)
    assert len(embeddings[0]) == 384
    assert repository.committed is True
