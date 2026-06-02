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
        "active": True,
    }


@pytest.mark.contract
def test_get_actor_reflects_deactivation() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client, name="Doga")
        client.post(f"/actors/{actor_id}/deactivate")
        response = client.get(f"/actors/{actor_id}")

    assert response.status_code == 200
    assert response.json()["active"] is False


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


# ---------- fix: service_account kind round-trip ----------


@pytest.mark.contract
def test_get_actor_returns_service_account_kind_end_to_end() -> None:
    """BLOCKING gate-review (design#1 + impl#1 + test#2): a
    service-account Actor registered via POST /actors must be
    successfully fetched via GET /actors/{id}. Pre-fix, the get_actor
    route DTO declared kind: Literal['human', 'agent'] only — a
    service_account row would fail Pydantic response validation -> 500."""
    from uuid import UUID as _UUID

    with TestClient(create_app()) as client:
        post = client.post("/actors", json={"name": "ci-bridge", "kind": "service_account"})
        assert post.status_code == 201
        actor_id = post.json()["actor_id"]
        _UUID(actor_id)  # parses

        got = client.get(f"/actors/{actor_id}")
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["kind"] == "service_account"
        assert body["name"] == "ci-bridge"
