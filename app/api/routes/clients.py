"""Client API routes."""

from fastapi import APIRouter, status

from app.api.dependencies import DatabaseSessionDependency
from app.repositories.clients import ClientRepository
from app.schemas.clients import ClientCreate, ClientRead
from app.services.clients import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, session: DatabaseSessionDependency) -> ClientRead:
    """Create an advisor client."""
    service = ClientService(ClientRepository(session))
    client = await service.create_client(payload)
    return ClientRead.model_validate(client)
