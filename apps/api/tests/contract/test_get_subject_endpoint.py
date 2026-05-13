"""Contract tests for `GET /subjects/{subject_id}`.

Mirrors `test_get_actor_endpoint.py`. Pinned response shape:
`{id, name, status}` where `status` is the StrEnum's string value
(Received / Mounted / Measured / ...).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._subject_helpers import register_active_asset


def _register_subject(client: TestClient, name: str = "Sample-A1") -> UUID:
    response = client.post("/subjects", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["subject_id"])


@pytest.mark.contract
def test_get_subject_returns_200_with_received_status_for_new_subject() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client, name="Sample-A1")
        response = client.get(f"/subjects/{subject_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(subject_id),
        "name": "Sample-A1",
        "status": "Received",
    }


@pytest.mark.contract
def test_get_subject_reflects_mount_transition() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_id = register_active_asset(client)
        client.post(f"/subjects/{subject_id}/mount", json={"asset_id": asset_id})
        response = client.get(f"/subjects/{subject_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "Mounted"


@pytest.mark.contract
def test_get_subject_reflects_full_lifecycle_to_returned() -> None:
    """End-to-end: register + mount + measure + remove + return.
    Pinned because each transition's evolver wiring must round-trip
    through the read side (regression guard against any future
    evolver edit that diverges from the write path)."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_id = register_active_asset(client)
        client.post(f"/subjects/{subject_id}/mount", json={"asset_id": asset_id})
        client.post(f"/subjects/{subject_id}/measure")
        client.post(f"/subjects/{subject_id}/remove")
        client.post(f"/subjects/{subject_id}/return")
        response = client.get(f"/subjects/{subject_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "Returned"


@pytest.mark.contract
def test_get_subject_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/subjects/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_subject_returns_422_for_malformed_subject_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/subjects/not-a-uuid")
    assert response.status_code == 422
