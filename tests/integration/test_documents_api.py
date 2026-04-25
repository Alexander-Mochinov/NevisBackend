"""Document API integration tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DocumentChunk


def valid_client_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Document",
        "last_name": "Client",
        "email": "document.client@neviswealth.test",
        "description": "Client with onboarding documents",
        "social_links": [],
    }
    payload.update(overrides)
    return payload


def valid_document_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Utility Bill",
        "content": (
            "The client uploaded a recent utility bill as proof of residence "
            "and address verification."
        ),
    }
    payload.update(overrides)
    return payload


async def create_client(api_client: AsyncClient) -> str:
    response = await api_client.post("/clients", json=valid_client_payload())
    assert response.status_code == 201
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_create_document_returns_201_for_existing_client(api_client: AsyncClient) -> None:
    client_id = await create_client(api_client)

    response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=valid_document_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["client_id"] == client_id
    assert body["title"] == "Utility Bill"
    assert body["content"] == valid_document_payload()["content"]
    assert body["summary"] == valid_document_payload()["content"]
    assert body["created_at"]


@pytest.mark.asyncio
async def test_create_document_unknown_client_returns_404(api_client: AsyncClient) -> None:
    unknown_client_id = uuid.uuid4()

    response = await api_client.post(
        f"/clients/{unknown_client_id}/documents",
        json=valid_document_payload(),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "client_not_found"


@pytest.mark.asyncio
async def test_create_document_missing_title_returns_422(api_client: AsyncClient) -> None:
    client_id = await create_client(api_client)
    payload = valid_document_payload()
    del payload["title"]

    response = await api_client.post(f"/clients/{client_id}/documents", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_document_empty_content_returns_422(api_client: AsyncClient) -> None:
    client_id = await create_client(api_client)

    response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=valid_document_payload(content="   "),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_document_creates_chunks(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client_id = await create_client(api_client)
    long_content = " ".join(
        [
            "The client uploaded a utility bill as proof of residence.",
            "The document confirms the current address for onboarding.",
            "The advisor reviewed the document for KYC compliance.",
            "The operations team marked the address verification as current.",
        ]
        * 20
    )

    response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=valid_document_payload(content=long_content),
    )
    document_id = uuid.UUID(response.json()["id"])

    async with integration_session_factory() as session:
        chunk_count = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )

    assert response.status_code == 201
    assert chunk_count is not None
    assert chunk_count > 1


@pytest.mark.asyncio
async def test_create_document_stores_chunk_embeddings(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client_id = await create_client(api_client)

    response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=valid_document_payload(),
    )
    document_id = uuid.UUID(response.json()["id"])

    async with integration_session_factory() as session:
        embedding = await session.scalar(
            select(DocumentChunk.embedding).where(DocumentChunk.document_id == document_id)
        )

    assert response.status_code == 201
    assert embedding is not None
    assert len(embedding) == 384


@pytest.mark.asyncio
async def test_create_document_summary_is_present(api_client: AsyncClient) -> None:
    client_id = await create_client(api_client)

    response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=valid_document_payload(),
    )

    assert response.status_code == 201
    assert response.json()["summary"]
