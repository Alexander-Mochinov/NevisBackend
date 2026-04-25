"""Public search API integration tests."""

import uuid

import pytest
from httpx import AsyncClient

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


async def seed_search_api_data(api_client: AsyncClient) -> tuple[uuid.UUID, uuid.UUID]:
    client_response = await api_client.post("/clients", json=CLIENT_PAYLOAD)
    assert client_response.status_code == 201
    client_id = uuid.UUID(client_response.json()["id"])

    document_response = await api_client.post(
        f"/clients/{client_id}/documents",
        json=DOCUMENT_PAYLOAD,
    )
    assert document_response.status_code == 201
    document_id = uuid.UUID(document_response.json()["id"])

    return client_id, document_id


@pytest.mark.asyncio
async def test_search_neviswealth_returns_client(api_client: AsyncClient) -> None:
    await seed_search_api_data(api_client)

    response = await api_client.get("/search", params={"q": "NevisWealth"})

    assert response.status_code == 200
    body = response.json()
    assert body
    client_result = _find_client_result(body, "sample.client@neviswealth.test")
    assert body.index(client_result) <= 1
    assert client_result["match_reason"] == "Matched email/domain"


@pytest.mark.asyncio
async def test_search_client_description_returns_client(api_client: AsyncClient) -> None:
    await seed_search_api_data(api_client)

    response = await api_client.get("/search", params={"q": "wealth management"})

    assert response.status_code == 200
    client_result = _find_client_result(response.json(), "sample.client@neviswealth.test")
    assert "description" in client_result["matched_fields"]


@pytest.mark.asyncio
async def test_search_address_proof_returns_utility_bill_document(
    api_client: AsyncClient,
) -> None:
    await seed_search_api_data(api_client)

    response = await api_client.get("/search", params={"q": "address proof"})

    assert response.status_code == 200
    utility_bill = _find_document_result(response.json(), "Utility Bill")
    assert utility_bill["document"]["best_chunk_excerpt"]
    assert utility_bill["match_reason"] in {
        "Semantic document match",
        "Synonym match: address proof \u2248 utility bill",
    }


@pytest.mark.asyncio
async def test_search_typo_utility_bill_uses_title_trigram(api_client: AsyncClient) -> None:
    await seed_search_api_data(api_client)

    response = await api_client.get("/search", params={"q": "utlity bil"})

    assert response.status_code == 200
    utility_bill = _find_document_result(response.json(), "Utility Bill")
    assert utility_bill["match_reason"] == "Matched document title"
    assert "title" in utility_bill["matched_fields"]


@pytest.mark.asyncio
async def test_search_empty_query_returns_400(api_client: AsyncClient) -> None:
    response = await api_client.get("/search", params={"q": "   "})

    assert response.status_code == 400
    assert response.json()["code"] == "empty_search_query"


@pytest.mark.asyncio
async def test_search_response_shape_scores_and_order(api_client: AsyncClient) -> None:
    await seed_search_api_data(api_client)

    response = await api_client.get("/search", params={"q": "NevisWealth"})

    assert response.status_code == 200
    body = response.json()
    scores = [result["score"] for result in body]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= score <= 1.0 for score in scores)

    first_result = body[0]
    for field in ("type", "id", "score", "match_reason", "matched_fields"):
        assert field in first_result


@pytest.mark.asyncio
async def test_search_explain_returns_pipeline_details(api_client: AsyncClient) -> None:
    await seed_search_api_data(api_client)

    response = await api_client.get(
        "/search",
        params={"q": "address proof", "explain": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "explanation" in body

    explanation = body["explanation"]
    assert explanation["normalized_query"] == "address proof"
    assert "utility bill" in explanation["expanded_queries"]
    assert any(
        channel["channel"] == "document_synonym"
        and channel["candidate_count"] >= 1
        for channel in explanation["channels"]
    )

    utility_bill = _find_document_result(body["results"], "Utility Bill")
    explained_result = next(
        result
        for result in explanation["results"]
        if result["result_id"].endswith(utility_bill["id"])
    )
    assert "document_synonym" in explained_result["channels"]
    assert "document_synonym" in explained_result["rrf_contributions"]


def _find_client_result(results: list[dict[str, object]], email: str) -> dict[str, object]:
    for result in results:
        client = result.get("client")
        if isinstance(client, dict) and client.get("email") == email:
            return result

    pytest.fail(f"Expected client result for {email}; got {results}")


def _find_document_result(results: list[dict[str, object]], title: str) -> dict[str, object]:
    for result in results:
        document = result.get("document")
        if isinstance(document, dict) and document.get("title") == title:
            return result

    pytest.fail(f"Expected document result for {title}; got {results}")
