"""Contract tests for `Idempotency-Key` support on `POST /actors`.

Mirrors the IETF draft / Stripe pattern:
- Same key + same body -> 201 with the same actor_id (no double-creation)
- Same key + different body -> 422
- Different keys -> different actors (independent requests)
- No key -> normal behaviour (each request creates a new actor)
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_actors_without_key_creates_distinct_actors_on_each_call() -> None:
    """Baseline: no Idempotency-Key means each POST creates a new actor."""
    with TestClient(create_app()) as client:
        r1 = client.post("/actors", json={"name": "Doga"})
        r2 = client.post("/actors", json={"name": "Doga"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["actor_id"] != r2.json()["actor_id"]


@pytest.mark.contract
def test_post_actors_same_key_and_body_returns_same_actor_id() -> None:
    """Retry with same Idempotency-Key + same body returns cached actor_id."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "test-key-1"}
        r1 = client.post("/actors", json={"name": "Doga"}, headers=headers)
        r2 = client.post("/actors", json={"name": "Doga"}, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["actor_id"] == r2.json()["actor_id"]


@pytest.mark.contract
def test_post_actors_same_key_different_body_returns_422() -> None:
    """Reusing a key with a different body is a client bug -> 422."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "test-key-2"}
        r1 = client.post("/actors", json={"name": "Doga"}, headers=headers)
        r2 = client.post("/actors", json={"name": "Other"}, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_actors_different_keys_create_distinct_actors() -> None:
    """Independent Idempotency-Keys produce independent results."""
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"Idempotency-Key": "key-A"},
        )
        r2 = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"Idempotency-Key": "key-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["actor_id"] != r2.json()["actor_id"]


@pytest.mark.contract
def test_post_actors_cached_response_returns_valid_uuid() -> None:
    """Cached actor_id must round-trip through the JSON cache as a parseable UUID."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "test-key-uuid"}
        r1 = client.post("/actors", json={"name": "Doga"}, headers=headers)
        r2 = client.post("/actors", json={"name": "Doga"}, headers=headers)

    UUID(r1.json()["actor_id"])  # parses
    UUID(r2.json()["actor_id"])  # parses
    assert r1.json()["actor_id"] == r2.json()["actor_id"]
