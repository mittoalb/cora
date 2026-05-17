"""Contract tests for `GET /agents/{agent_id}` (Phase 8f-a)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "RunDebrief",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_get_agents_returns_200_and_dto() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        assert define.status_code == 201, define.text
        agent_id = define.json()["agent_id"]
        response = client.get(f"/agents/{agent_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == agent_id
    assert body["kind"] == "RunDebrief"
    assert body["name"] == "Run Debrief"
    assert body["version"] == "v1"
    assert body["status"] == "Defined"
    assert body["model_ref"] == {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "snapshot_pin": None,
    }
    assert body["capabilities"] == []
    assert body["description"] is None
    assert body["canonical_uri"] is None


@pytest.mark.contract
def test_get_agents_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/agents/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.contract
def test_get_agents_after_version_returns_versioned_status() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        version_resp = client.post(f"/agents/{agent_id}/version")
        assert version_resp.status_code == 204
        get_resp = client.get(f"/agents/{agent_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "Versioned"
    assert get_resp.json()["versioned_at"] is not None
