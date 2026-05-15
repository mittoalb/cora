"""Contract tests for `POST /procedures/{procedure_id}/start`.

Action endpoint, no body, 204 on success. Covers happy path
(facility-envelope procedure that has no target Assets) plus the
error surfaces: 404 unknown procedure, 409 re-start, 422 malformed
id.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_procedure(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "Beam-mode change to white", "kind": "beam_mode_change"}
    response = client.post("/procedures", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["procedure_id"])


@pytest.mark.contract
def test_post_start_returns_204_for_defined_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_procedure(client)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_start_marks_status_running_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_procedure(client)
        client.post(f"/procedures/{pid}/start")
        response = client.get(f"/procedures/{pid}")
    assert response.status_code == 200
    assert response.json()["status"] == "Running"


@pytest.mark.contract
def test_post_start_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/start")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_start_returns_409_when_re_starting_running() -> None:
    with TestClient(create_app()) as client:
        pid = _register_procedure(client)
        first = client.post(f"/procedures/{pid}/start")
        second = client.post(f"/procedures/{pid}/start")
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_start_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/start")
    assert response.status_code == 422
