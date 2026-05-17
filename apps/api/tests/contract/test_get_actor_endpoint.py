"""Contract tests for `GET /actors/{actor_id}`."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_actor(client: TestClient, name: str = "Doga") -> UUID:
    response = client.post("/actors", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["actor_id"])


@pytest.mark.contract
def test_get_actor_returns_200_with_actor_response() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client, name="Doga")
        response = client.get(f"/actors/{actor_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(actor_id),
        "name": "Doga",
        "kind": "human",
        "is_active": True,
    }


@pytest.mark.contract
def test_get_actor_reflects_deactivation() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client, name="Doga")
        client.post(f"/actors/{actor_id}/deactivate")
        response = client.get(f"/actors/{actor_id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.contract
def test_get_actor_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/actors/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_actor_returns_422_for_malformed_actor_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/actors/not-a-uuid")
    assert response.status_code == 422
