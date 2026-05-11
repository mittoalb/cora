"""Contract tests for `GET /capabilities/{capability_id}`.

Mirrors `test_get_subject_endpoint.py` / `test_get_actor_endpoint.py`.
Pinned response shape: `{id, name, status}` where `status` is the
StrEnum's string value (Defined / Versioned / Deprecated).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_capability(client: TestClient, name: str = "Tomography") -> UUID:
    response = client.post("/capabilities", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["capability_id"])


@pytest.mark.contract
def test_get_capability_returns_200_with_defined_status_for_new_capability() -> None:
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client, name="Tomography")
        response = client.get(f"/capabilities/{capability_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(capability_id),
        "name": "Tomography",
        "status": "Defined",
        # Null until version_capability runs (5f-2).
        "current_version": None,
    }


@pytest.mark.contract
def test_get_capability_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/capabilities/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_capability_returns_422_for_malformed_capability_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/capabilities/not-a-uuid")
    assert response.status_code == 422
