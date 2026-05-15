"""Contract tests for `POST /procedures/{procedure_id}/complete`.

Action endpoint, no body, 204 on success. Covers happy path (after
register + start) plus error surfaces: 404, 409 from-Defined, 409
re-complete, 422 malformed id.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_and_start(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    response = client.post("/procedures", json=body)
    assert response.status_code == 201, response.text
    pid = UUID(response.json()["procedure_id"])
    started = client.post(f"/procedures/{pid}/start")
    assert started.status_code == 204, started.text
    return pid


@pytest.mark.contract
def test_post_complete_returns_204_for_running_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/complete")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_complete_marks_status_completed_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        client.post(f"/procedures/{pid}/complete")
        response = client.get(f"/procedures/{pid}")
    assert response.json()["status"] == "Completed"


@pytest.mark.contract
def test_post_complete_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/complete")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_complete_returns_409_for_defined_procedure() -> None:
    """complete requires Running; from Defined raises CannotComplete."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        response = client.post(f"/procedures/{pid}/complete")
    assert response.status_code == 409


@pytest.mark.contract
def test_post_complete_returns_409_when_re_completing() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        first = client.post(f"/procedures/{pid}/complete")
        second = client.post(f"/procedures/{pid}/complete")
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_complete_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/complete")
    assert response.status_code == 422
