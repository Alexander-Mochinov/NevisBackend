"""OpenAPI and route validation tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
async def test_openapi_schema_includes_required_endpoints() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/clients" in paths
    assert "/clients/{client_id}/documents" in paths
    assert "/search" in paths
    assert "/health" in paths


@pytest.mark.asyncio
async def test_search_requires_query_parameter() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search")

    assert response.status_code == 422
