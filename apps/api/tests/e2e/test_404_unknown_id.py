"""E2E smoke: GET against an unknown aggregate returns 404.

Pinned: missing-aggregate maps to a 404 with a `detail` payload that
contains "not found" (case-insensitive). Same shape as the contract
test for `GET /actors/{actor_id}`.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_get_unknown_actor_returns_404(e2e_client: AsyncClient) -> None:
    response = await e2e_client.get(f"/actors/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()
