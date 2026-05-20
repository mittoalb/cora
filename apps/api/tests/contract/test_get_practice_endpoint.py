"""Contract tests for `GET /practices/{practice_id}`.

Pinned response shape: `{id, name, method_id, site_id, status, version}`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_practice(
    client: TestClient,
    *,
    name: str = "APS Standard Tomography",
    method_id: str | None = None,
    site_id: str | None = None,
) -> tuple[UUID, str, str]:
    method_id = method_id or str(uuid4())
    site_id = site_id or str(uuid4())
    response = client.post(
        "/practices",
        json={"name": name, "method_id": method_id, "site_id": site_id},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["practice_id"]), method_id, site_id


@pytest.mark.contract
def test_get_practice_returns_200_with_defined_status_for_new_practice() -> None:
    with TestClient(create_app()) as client:
        practice_id, method_id, site_id = _define_practice(client, name="APS Standard Tomography")
        response = client.get(f"/practices/{practice_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(practice_id),
        "name": "APS Standard Tomography",
        "method_id": method_id,
        "site_id": site_id,
        "status": "Defined",
        # Null until version_practice runs (6d-2).
        "version": None,
        # Projection-sourced timestamps; null in contract tests (no DB pool).
        # Populated values asserted in tests/integration/test_get_practice_handler_postgres.py.
        "created_at": None,
        "versioned_at": None,
        "deprecated_at": None,
    }


@pytest.mark.contract
def test_get_practice_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/practices/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_practice_returns_422_for_malformed_practice_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/practices/not-a-uuid")
    assert response.status_code == 422
