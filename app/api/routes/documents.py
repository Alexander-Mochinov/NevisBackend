"""Document API routes."""

import uuid

from fastapi import APIRouter, status

from app.api.dependencies import DatabaseSessionDependency, SettingsDependency
from app.repositories.documents import DocumentRepository
from app.schemas.documents import DocumentCreate, DocumentRead
from app.services.chunking_service import ChunkingService
from app.services.documents import DocumentService
from app.services.embedding_service import create_embedding_provider
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/clients/{client_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    client_id: uuid.UUID,
    payload: DocumentCreate,
    session: DatabaseSessionDependency,
    settings: SettingsDependency,
) -> DocumentRead:
    """Create a document for an existing client."""
    service = DocumentService(
        repository=DocumentRepository(session),
        chunking_service=ChunkingService(),
        embedding_provider=create_embedding_provider(settings),
        summary_service=SummaryService(),
    )
    document = await service.create_document(client_id=client_id, payload=payload)
    return DocumentRead.model_validate(document)
