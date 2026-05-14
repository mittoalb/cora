"""E2E smoke: Idempotency-Key replay returns the cached actor_id.

Same key + same body must return the same actor_id and not create a
second aggregate. Mirrors the contract-tier test against the full
HTTP -> handler -> Postgres -> idempotency cache stack.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_post_actors_same_key_returns_same_id_no_duplicate(
    e2e_client: AsyncClient,
    e2e_drain: Callable[[], Awaitable[None]],
) -> None:
    headers = {"Idempotency-Key": "e2e-replay-1"}
    body = {"name": "Doga"}

    r1 = await e2e_client.post("/actors", json=body, headers=headers)
    r2 = await e2e_client.post("/actors", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    actor_id = UUID(r1.json()["actor_id"])
    assert UUID(r2.json()["actor_id"]) == actor_id

    # No duplicate aggregate landed in the projection.
    await e2e_drain()
    listed = await e2e_client.get("/actors")
    assert listed.status_code == 200
    items = listed.json()["items"]
    matches = [item for item in items if item["actor_id"] == str(actor_id)]
    assert len(matches) == 1
