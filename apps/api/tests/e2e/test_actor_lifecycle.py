"""E2E smoke: register actor -> get -> list (projection-backed).

Verifies the full HTTP -> handler -> Postgres -> projection -> query
path for the canonical "easiest BC" path. The list step exercises the
projection worker via the e2e_drain fixture so the assertion doesn't
race the in-process worker.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_register_then_get_then_list(
    e2e_client: AsyncClient,
    e2e_drain: Callable[[], Awaitable[None]],
) -> None:
    register = await e2e_client.post("/actors", json={"name": "Doga"})
    assert register.status_code == 201
    actor_id = UUID(register.json()["actor_id"])

    # GET reads the write side directly (no projection involved).
    fetched = await e2e_client.get(f"/actors/{actor_id}")
    assert fetched.status_code == 200
    assert fetched.json() == {
        "id": str(actor_id),
        "name": "Doga",
        "kind": "human",
        "active": True,
    }

    # LIST is projection-backed; drain so the bookmark catches up before
    # the test asserts presence in the page.
    await e2e_drain()
    listed = await e2e_client.get("/actors")
    assert listed.status_code == 200
    body = listed.json()
    assert any(item["actor_id"] == str(actor_id) for item in body["items"])
