"""Document use cases."""

import asyncio
import uuid

from fastapi import status

from app.core.errors import AppError
from app.models import Document
from app.repositories.documents import DocumentRepository
from app.schemas.documents import DocumentCreate
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingProvider
from app.services.summary_service import SummaryService


class DocumentService:
    """Business operations for documents."""

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        chunking_service: ChunkingService,
        embedding_provider: EmbeddingProvider,
        summary_service: SummaryService,
    ) -> None:
        self._repository = repository
        self._chunking_service = chunking_service
        self._embedding_provider = embedding_provider
        self._summary_service = summary_service

    async def create_document(self, *, client_id: uuid.UUID, payload: DocumentCreate) -> Document:
        if not await self._repository.client_exists(client_id):
            raise AppError(
                code="client_not_found",
                message="Client not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        chunks = self._chunking_service.chunk_text(payload.content)
        embeddings = await asyncio.to_thread(self._embedding_provider.encode_documents, chunks)
        summary = self._summary_service.summarize(payload.content)

        try:
            document = await self._repository.create_document(
                client_id=client_id,
                title=payload.title,
                content=payload.content,
                summary=summary,
                chunks=chunks,
                embeddings=embeddings,
            )
            await self._repository.commit()
        except Exception:
            await self._repository.rollback()
            raise

        return document
