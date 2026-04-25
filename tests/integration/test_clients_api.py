"""Client API integration tests."""

import pytest
from httpx import AsyncClient


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Sample",
        "last_name": "Client",
        "email": "sample.client@neviswealth.test",
        "description": "Wealth management client",
        "social_links": ["https://example.test/profiles/sample-client"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_client_returns_201(api_client: AsyncClient) -> None:
    response = await api_client.post("/clients", json=valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["first_name"] == "Sample"
    assert body["last_name"] == "Client"
    assert body["email"] == "sample.client@neviswealth.test"
    assert body["description"] == "Wealth management client"
    assert body["social_links"] == ["https://example.test/profiles/sample-client"]
    assert body["created_at"]
    assert body["updated_at"]


@pytest.mark.asyncio
async def test_create_client_normalizes_email(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/clients",
        json=valid_payload(email="Sample.Client@NevisWealth.TEST"),
    )

    assert response.status_code == 201
    assert response.json()["email"] == "sample.client@neviswealth.test"


@pytest.mark.asyncio
async def test_create_client_duplicate_email_returns_409(api_client: AsyncClient) -> None:
    first_response = await api_client.post("/clients", json=valid_payload())
    duplicate_response = await api_client.post(
        "/clients",
        json=valid_payload(email="SAMPLE.CLIENT@NEVISWEALTH.TEST"),
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["code"] == "client_email_conflict"


@pytest.mark.asyncio
async def test_create_client_invalid_email_returns_422(api_client: AsyncClient) -> None:
    response = await api_client.post("/clients", json=valid_payload(email="not-an-email"))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_client_missing_first_name_returns_422(api_client: AsyncClient) -> None:
    payload = valid_payload()
    del payload["first_name"]

    response = await api_client.post("/clients", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_client_empty_names_return_422(api_client: AsyncClient) -> None:
    first_name_response = await api_client.post("/clients", json=valid_payload(first_name=""))
    last_name_response = await api_client.post("/clients", json=valid_payload(last_name="   "))

    assert first_name_response.status_code == 422
    assert last_name_response.status_code == 422
