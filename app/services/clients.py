"""Client use cases."""

from fastapi import status

from app.core.errors import AppError
from app.models import Client
from app.repositories.clients import ClientRepository, DuplicateClientEmailError
from app.schemas.clients import ClientCreate


class ClientService:
    """Business operations for clients."""

    def __init__(self, repository: ClientRepository) -> None:
        self._repository = repository

    async def create_client(self, payload: ClientCreate) -> Client:
        try:
            client = await self._repository.create_client(
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=str(payload.email).lower(),
                description=payload.description,
                social_links=payload.social_links,
            )
            await self._repository.commit()
        except DuplicateClientEmailError as exc:
            raise AppError(
                code="client_email_conflict",
                message="A client with this email already exists.",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        return client
