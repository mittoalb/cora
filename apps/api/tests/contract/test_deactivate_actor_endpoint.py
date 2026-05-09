"""Contract tests for `POST /actors/{actor_id}/deactivate`.

Mirrors the test_actors_endpoint.py shape: TestClient context manager
runs the lifespan with APP_ENV=test (InMemoryEventStore), HTTP-level
assertions only, persistence verified by handler unit tests.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_actor(client: TestClient) -> UUID:
    """Helper: register an actor and return its id."""
    response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 201
    return UUID(response.json()["actor_id"])


@pytest.mark.contract
def test_post_deactivate_returns_204_for_active_actor() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post(f"/actors/{actor_id}/deactivate")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_deactivate_returns_404_for_unknown_actor() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/actors/{uuid4()}/deactivate")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_post_deactivate_returns_409_when_already_deactivated() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        first = client.post(f"/actors/{actor_id}/deactivate")
        assert first.status_code == 204
        second = client.post(f"/actors/{actor_id}/deactivate")
    assert second.status_code == 409
    body = second.json()
    assert "detail" in body
    assert "already deactivated" in body["detail"].lower()


@pytest.mark.contract
def test_post_deactivate_returns_422_for_malformed_actor_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/actors/not-a-uuid/deactivate")
    assert response.status_code == 422
