"""Small search relevance snapshot over a mixed demo corpus."""

import uuid

import pytest
from httpx import AsyncClient

CLIENT_PAYLOAD: dict[str, object] = {
    "first_name": "Sample",
    "last_name": "Client",
    "email": "sample.client@neviswealth.test",
    "description": "Wealth management client with onboarding documents",
    "social_links": ["https://example.test/profiles/sample-client"],
}

DOCUMENTS: tuple[dict[str, str], ...] = (
    {
        "title": "Utility Bill",
        "content": (
            "The client uploaded a recent utility bill as proof of residence "
            "and address verification."
        ),
    },
    {
        "title": "Passport",
        "content": "The passport confirms identity and supports proof of identity checks.",
    },
    {
        "title": "Bank Statement",
        "content": "The bank statement confirms account ownership and banking details.",
    },
    {
        "title": "Portfolio Review",
        "content": "Quarterly portfolio review notes covering allocation and performance.",
    },
)


@pytest.mark.asyncio
async def test_relevance_address_proof_ranks_utility_bill_above_unrelated_document(
    api_client: AsyncClient,
) -> None:
    await seed_relevance_data(api_client)

    response = await api_client.get("/search", params={"q": "address proof"})

    assert response.status_code == 200
    results = response.json()
    utility_bill_index = _document_index(results, "Utility Bill")
    portfolio_index = _optional_document_index(results, "Portfolio Review")
    if portfolio_index is not None:
        assert utility_bill_index < portfolio_index


@pytest.mark.asyncio
async def test_relevance_id_proof_finds_passport(api_client: AsyncClient) -> None:
    await seed_relevance_data(api_client)

    response = await api_client.get("/search", params={"q": "id proof"})

    assert response.status_code == 200
    passport = _find_document(response.json(), "Passport")
    assert "passport" in passport["document"]["title"].lower()


@pytest.mark.asyncio
async def test_relevance_bank_proof_finds_bank_statement(api_client: AsyncClient) -> None:
    await seed_relevance_data(api_client)

    response = await api_client.get("/search", params={"q": "bank proof"})

    assert response.status_code == 200
    bank_statement = _find_document(response.json(), "Bank Statement")
    assert bank_statement["document"]["title"] == "Bank Statement"


@pytest.mark.asyncio
async def test_relevance_typo_finds_utility_bill_title(api_client: AsyncClient) -> None:
    await seed_relevance_data(api_client)

    response = await api_client.get("/search", params={"q": "utlity bil"})

    assert response.status_code == 200
    utility_bill = _find_document(response.json(), "Utility Bill")
    assert utility_bill["match_reason"] == "Matched document title"


async def seed_relevance_data(api_client: AsyncClient) -> uuid.UUID:
    client_response = await api_client.post("/clients", json=CLIENT_PAYLOAD)
    assert client_response.status_code == 201
    client_id = uuid.UUID(client_response.json()["id"])

    for document in DOCUMENTS:
        document_response = await api_client.post(
            f"/clients/{client_id}/documents",
            json=document,
        )
        assert document_response.status_code == 201

    return client_id


def _find_document(results: list[dict[str, object]], title: str) -> dict[str, object]:
    for result in results:
        document = result.get("document")
        if isinstance(document, dict) and document.get("title") == title:
            return result

    pytest.fail(f"Expected document result for {title}; got {results}")


def _document_index(results: list[dict[str, object]], title: str) -> int:
    return results.index(_find_document(results, title))


def _optional_document_index(results: list[dict[str, object]], title: str) -> int | None:
    for index, result in enumerate(results):
        document = result.get("document")
        if isinstance(document, dict) and document.get("title") == title:
            return index
    return None
