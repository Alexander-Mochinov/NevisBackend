"""Hybrid search retrieval integration tests."""

import uuid
from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.search import SearchRepository
from app.search.types import SearchCandidate, SearchChannel, SearchResultType
from app.services.embedding_service import FakeEmbeddingProvider
from app.services.search import SearchService


@dataclass(frozen=True)
class SeededSearchData:
    """Seed identifiers for search retrieval tests."""

    client_id: uuid.UUID
    document_id: uuid.UUID


CLIENT_PAYLOAD: dict[str, object] = {
    "first_name": "Sample",
    "last_name": "Client",
    "email": "sample.client@neviswealth.test",
    "description": "Wealth management client",
    "social_links": ["https://example.test/profiles/sample-client"],
}

DOCUMENT_PAYLOAD: dict[str, object] = {
    "title": "Utility Bill",
    "content": (
        "The client uploaded a recent utility bill as proof of residence and "
        "address verification."
    ),
}


async def seed_search_data(api_client: AsyncClient) -> SeededSearchData:
    client_response = await api_client.post("/clients", json=CLIENT_PAYLOAD)
    assert client_response.status_code == 201
    client_id = uuid.UUID(client_response.json()["id"])

    document_response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=DOCUMENT_PAYLOAD,
    )
    assert document_response.status_code == 201
    document_id = uuid.UUID(document_response.json()["id"])

    return SeededSearchData(client_id=client_id, document_id=document_id)


@pytest.mark.asyncio
async def test_client_exact_finds_sample_client_by_neviswealth(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await seed_search_data(api_client)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        candidates = await repository.client_exact("neviswealth")

    candidate = _find_candidate(candidates, seeded.client_id)
    assert candidate.result_type == SearchResultType.CLIENT
    assert candidate.payload["email"] == "sample.client@neviswealth.test"
    assert "email" in candidate.matched_fields


@pytest.mark.asyncio
async def test_client_exact_finds_sample_client_by_first_name(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await seed_search_data(api_client)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        candidates = await repository.client_exact("sample")

    candidate = _find_candidate(candidates, seeded.client_id)
    assert candidate.payload["full_name"] == "Sample Client"
    assert "first_name" in candidate.matched_fields


@pytest.mark.asyncio
async def test_client_trigram_finds_typo_like_domain(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await seed_search_data(api_client)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        candidates = await repository.client_trigram("neviswelth")

    candidate = _find_candidate(candidates, seeded.client_id)
    assert candidate.channel == SearchChannel.CLIENT_TRIGRAM
    assert candidate.raw_score > 0.0


@pytest.mark.asyncio
async def test_document_fulltext_finds_utility_bill(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await seed_search_data(api_client)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        candidates = await repository.document_fulltext("utility bill")

    candidate = _find_candidate(candidates, seeded.document_id)
    assert candidate.result_type == SearchResultType.DOCUMENT
    assert candidate.payload["title"] == "Utility Bill"


@pytest.mark.asyncio
async def test_document_synonym_retrieves_utility_bill_for_address_proof(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await seed_search_data(api_client)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        service = SearchService(
            repository=repository,
            embedding_provider=FakeEmbeddingProvider(dimension=384),
        )
        result = await service.retrieve_candidates("address proof")

    synonym_candidates = result.candidates_by_channel[SearchChannel.DOCUMENT_SYNONYM]
    candidate = _find_candidate(synonym_candidates, seeded.document_id)
    assert candidate.payload["title"] == "Utility Bill"
    assert "synonym:utility bill" in candidate.matched_fields


@pytest.mark.asyncio
async def test_document_vector_returns_document_candidate(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await seed_search_data(api_client)
    embedding_provider = FakeEmbeddingProvider(dimension=384)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        candidates = await repository.document_vector(
            embedding_provider.encode_query("utility bill")
        )

    candidate = _find_candidate(candidates, seeded.document_id)
    assert candidate.channel == SearchChannel.DOCUMENT_VECTOR
    assert candidate.matched_fields == ("chunk.embedding",)


@pytest.mark.asyncio
async def test_unknown_query_does_not_crash_retrieval(
    api_client: AsyncClient,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await seed_search_data(api_client)

    async with integration_session_factory() as session:
        repository = SearchRepository(session)
        service = SearchService(
            repository=repository,
            embedding_provider=FakeEmbeddingProvider(dimension=384),
        )
        result = await service.retrieve_candidates("zzzxqvnotfound")

    assert result.query == "zzzxqvnotfound"
    assert result.expanded_queries == ("zzzxqvnotfound",)
    assert result.candidates_by_channel[SearchChannel.CLIENT_EXACT] == ()
    assert result.candidates_by_channel[SearchChannel.CLIENT_FULLTEXT] == ()
    assert result.candidates_by_channel[SearchChannel.DOCUMENT_FULLTEXT] == ()
    assert result.candidates_by_channel[SearchChannel.DOCUMENT_SYNONYM] == ()


def _find_candidate(
    candidates: tuple[SearchCandidate, ...],
    candidate_id: uuid.UUID,
) -> SearchCandidate:
    for candidate in candidates:
        if candidate.id == candidate_id:
            return candidate

    candidate_ids = [str(candidate.id) for candidate in candidates]
    pytest.fail(f"Expected candidate {candidate_id}; got {candidate_ids}")
