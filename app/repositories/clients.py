"""Client persistence."""

import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client


class DuplicateClientEmailError(Exception):
    """Raised when a client email violates the unique constraint."""


class ClientRepository:
    """Database operations for clients."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_client(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        description: str | None,
        social_links: list[str] | None,
    ) -> Client:
        client = Client(
            first_name=first_name,
            last_name=last_name,
            email=email,
            description=description,
            social_links=social_links,
        )
        self._session.add(client)

        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateClientEmailError from exc

        await self._update_search_vector(client.id)
        await self._session.refresh(client)
        return client

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def _update_search_vector(self, client_id: uuid.UUID) -> None:
        await self._session.execute(
            text(
                """
                UPDATE clients
                SET search_vector = to_tsvector(
                    'simple',
                    concat_ws(' ', first_name, last_name, email, coalesce(description, ''))
                )
                WHERE id = :client_id
                """
            ),
            {"client_id": client_id},
        )
