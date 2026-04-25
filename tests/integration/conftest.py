"""Integration test fixtures."""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import get_session
from app.main import create_app


class SessionOverride:
    """FastAPI dependency override that reuses the integration session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session


def database_url() -> str:
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 to run database integration tests.")

    configured_database_url = os.getenv("DATABASE_URL")
    if not configured_database_url:
        pytest.skip("DATABASE_URL is required for database integration tests.")

    return configured_database_url


@pytest_asyncio.fixture
async def integration_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url(), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    await truncate_tables(session_factory)
    yield session_factory
    await truncate_tables(session_factory)
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_session] = SessionOverride(integration_session_factory)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def truncate_tables(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Reset integration tables between tests."""
    async with session_factory() as session:
        await session.execute(text("TRUNCATE TABLE document_chunks, documents, clients CASCADE"))
        await session.commit()
