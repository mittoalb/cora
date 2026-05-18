"""Contract tests for `GET /families/{family_id}`.

Mirrors `test_get_subject_endpoint.py` / `test_get_actor_endpoint.py`.
Pinned response shape: `{id, name, status}` where `status` is the
StrEnum's string value (Defined / Versioned / Deprecated).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_family(client: TestClient, name: str = "Tomography") -> UUID:
    response = client.post("/families", json={"name": name, "affordances": []})
    assert response.status_code == 201
    return UUID(response.json()["family_id"])


@pytest.mark.contract
def test_get_family_returns_200_with_defined_status_for_new_capability() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client, name="Tomography")
        response = client.get(f"/families/{family_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(family_id),
        "name": "Tomography",
        "status": "Defined",
        # Null until version_family runs (5f-2).
        "version": None,
        # Phase 5j: empty frozenset at define_family time renders as [].
        "affordances": [],
    }


@pytest.mark.contract
def test_get_family_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/families/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_family_returns_422_for_malformed_family_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/families/not-a-uuid")
    assert response.status_code == 422
