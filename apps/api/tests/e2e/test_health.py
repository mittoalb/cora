"""E2E smoke: health endpoint proves the app boots end-to-end."""

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_health_returns_ok(e2e_client: AsyncClient) -> None:
    response = await e2e_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
