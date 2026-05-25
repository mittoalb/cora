# pyright: reportPrivateUsage=false

"""Contract test for the 409 Conflict + `Retry-After: 1` response
emitted when an Idempotency-Key claim race is lost.

When one request holds the in-flight lock for a key and a second
request arrives with the same key, the second request returns 409
Conflict with `Retry-After: 1` (RFC 9110 standard). HTTP-conformant
SDKs auto-retry after the delay; the next claim either finds the
original request completed (cache hit -> same response) or takes
over a stale lock (worker crashed mid-handler).

Tests inject a locked row directly into the in-memory store rather
than racing two real concurrent requests, because the test client
is synchronous and the in-memory store is thread-locked. The
decorator's claim-lost path is exercised end-to-end: route ->
decorator -> store.claim() -> LockedRecent -> raise
IdempotencyClaimLostError -> Access global handler -> 409 + header.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore, _Row
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID

_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000099")


def _seed_locked_row(store: InMemoryIdempotencyStore, key: str) -> None:
    """Inject a fresh in-flight row simulating a concurrent request
    that has just claimed the lock and is mid-handler.

    Seeded under HTTP surface — the TestClient invokes the FastAPI
    route which calls `get_surface_id` returning SYSTEM_HTTP_SURFACE_ID,
    so the cache slot under which `with_idempotency` looks must
    match this surface for the LockedRecent path to fire."""
    now = datetime.now(tz=UTC)
    store._records[(_PRINCIPAL_ID, key, SYSTEM_HTTP_SURFACE_ID)] = _Row(
        command_hash="seeded-hash",
        command_name="RegisterActor",
        created_at=now,
        locked_at=now,
    )


@pytest.mark.contract
def test_post_actors_returns_409_with_retry_after_when_claim_lost() -> None:
    """Locked-row injection simulates a concurrent in-flight request.
    The second POST should receive 409 + `Retry-After: 1`."""
    with TestClient(create_app()) as client:
        store = client.app.state.deps.idempotency_store  # type: ignore[attr-defined]
        assert isinstance(store, InMemoryIdempotencyStore)
        _seed_locked_row(store, "race-key")

        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={
                "Idempotency-Key": "race-key",
                "X-Principal-Id": str(_PRINCIPAL_ID),
            },
        )

    assert response.status_code == 409
    assert response.headers.get("Retry-After") == "1"
    body = response.json()
    assert "detail" in body
    assert "race-key" in body["detail"]


@pytest.mark.contract
def test_409_response_body_does_not_leak_internal_state() -> None:
    """The error body should mention the key and that retry is
    expected. Sanity check on response shape."""
    with TestClient(create_app()) as client:
        store = client.app.state.deps.idempotency_store  # type: ignore[attr-defined]
        assert isinstance(store, InMemoryIdempotencyStore)
        _seed_locked_row(store, "diag-key")

        response = client.post(
            "/actors",
            json={"name": "X"},
            headers={
                "Idempotency-Key": "diag-key",
                "X-Principal-Id": str(_PRINCIPAL_ID),
            },
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "diag-key" in detail
    assert "retry" in detail.lower()
