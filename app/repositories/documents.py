"""Document persistence."""

import uuid

from sqlalchemy import exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Document, DocumentChunk


class DocumentRepository:
    """Database operations for documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def client_exists(self, client_id: uuid.UUID) -> bool:
        statement = select(exists().where(Client.id == client_id))
        return bool(await self._session.scalar(statement))

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
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        document = Document(
            client_id=client_id,
            title=title,
            content=content,
            summary=summary,
        )
        self._session.add(document)
        await self._session.flush()

        chunk_models = [
            DocumentChunk(
                document_id=document.id,
                client_id=client_id,
                chunk_index=index,
                content=chunk,
                embedding=embeddings[index],
            )
            for index, chunk in enumerate(chunks)
        ]
        self._session.add_all(chunk_models)
        await self._session.flush()

        await self._update_document_search_vector(document.id)
        await self._update_chunk_search_vectors(document.id)
        await self._session.refresh(document)
        return document

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def _update_document_search_vector(self, document_id: uuid.UUID) -> None:
        await self._session.execute(
            text(
                """
                UPDATE documents
                SET search_vector = to_tsvector(
                    'simple',
                    concat_ws(' ', title, content, coalesce(summary, ''))
                )
                WHERE id = :document_id
                """
            ),
            {"document_id": document_id},
        )

    async def _update_chunk_search_vectors(self, document_id: uuid.UUID) -> None:
        await self._session.execute(
            text(
                """
                UPDATE document_chunks
                SET search_vector = to_tsvector('simple', content)
                WHERE document_id = :document_id
                """
            ),
            {"document_id": document_id},
        )
