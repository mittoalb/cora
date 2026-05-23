"""Contract tests for `DELETE /actors/{actor_id}/profile` (forget_actor).

Verifies the HTTP surface: request schema, response codes, and that
the route delegates to the wired idempotent handler. Persistence +
single-transaction atomicity are covered by the unit + integration
tests for the handler; this file does not re-verify what landed in
the store.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_delete_actor_profile_returns_204_after_register() -> None:
    """Round-trip: register an actor through the API, then erase
    their PII vault row. Both succeed; the response is 204 No
    Content as documented in the route signature."""
    with TestClient(create_app()) as client:
        registered = client.post("/actors", json={"name": "Doga"})
        assert registered.status_code == 201
        actor_id = UUID(registered.json()["actor_id"])

        response = client.delete(f"/actors/{actor_id}/profile")

    assert response.status_code == 204
    assert response.text == ""


@pytest.mark.contract
def test_delete_actor_profile_unknown_id_returns_404() -> None:
    """No prior register -> ActorNotFoundError -> 404 from the
    Access BC's shared exception handler."""
    unknown = uuid4()
    with TestClient(create_app()) as client:
        response = client.delete(f"/actors/{unknown}/profile")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_delete_actor_profile_invalid_uuid_returns_422() -> None:
    """FastAPI path-parameter validation catches non-UUID input."""
    with TestClient(create_app()) as client:
        response = client.delete("/actors/not-a-uuid/profile")
    assert response.status_code == 422


@pytest.mark.contract
def test_delete_actor_profile_accepts_idempotency_key_header() -> None:
    """Idempotency-Key is documented in the route and gets threaded
    through the wired idempotent handler. The wire-level cache
    short-circuits a second call with the same key + same target."""
    key = "forget-actor-double-click-test-001"
    with TestClient(create_app()) as client:
        registered = client.post("/actors", json={"name": "Doga"})
        actor_id = UUID(registered.json()["actor_id"])

        first = client.delete(
            f"/actors/{actor_id}/profile",
            headers={"Idempotency-Key": key},
        )
        second = client.delete(
            f"/actors/{actor_id}/profile",
            headers={"Idempotency-Key": key},
        )

    assert first.status_code == 204
    assert second.status_code == 204  # cache replay; identical response
