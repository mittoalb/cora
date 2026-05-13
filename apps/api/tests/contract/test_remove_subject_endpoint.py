"""Contract tests for `POST /subjects/{subject_id}/remove`.

Mirrors `test_mount_subject_endpoint.py`. Covers both source states
of the multi-source-state guard (Mounted -> Removed and Measured ->
Removed) plus the disallowed-source error mapping.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._subject_helpers import register_active_asset


def _register_subject(client: TestClient, name: str = "Sample-A1") -> str:
    response = client.post("/subjects", json={"name": name})
    assert response.status_code == 201
    subject_id: str = response.json()["subject_id"]
    return subject_id


def _register_and_mount(client: TestClient) -> str:
    subject_id = _register_subject(client)
    asset_id = register_active_asset(client)
    mounted = client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": asset_id}
    )
    assert mounted.status_code == 204
    return subject_id


def _register_mount_measure(client: TestClient) -> str:
    subject_id = _register_and_mount(client)
    measured = client.post(f"/subjects/{subject_id}/measure")
    assert measured.status_code == 204
    return subject_id


@pytest.mark.contract
def test_post_remove_returns_204_from_mounted_state() -> None:
    """Mounted -> Removed (skipping measure)."""
    with TestClient(create_app()) as client:
        subject_id = _register_and_mount(client)
        response = client.post(f"/subjects/{subject_id}/remove")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_remove_returns_204_from_measured_state() -> None:
    """Full happy path: Measured -> Removed."""
    with TestClient(create_app()) as client:
        subject_id = _register_mount_measure(client)
        response = client.post(f"/subjects/{subject_id}/remove")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_remove_returns_404_when_subject_does_not_exist() -> None:
    """SubjectNotFoundError -> 404 via the BC's exception handler."""
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/subjects/{missing_id}/remove")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_remove_returns_409_when_subject_only_received() -> None:
    """SubjectCannotRemoveError on Received subject -> 409. Pinned
    because the multi-source-state guard means the error message
    must list BOTH allowed source states."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post(f"/subjects/{subject_id}/remove")
    assert response.status_code == 409
    body = response.json()
    assert "Received" in body["detail"]
    assert "Mounted" in body["detail"]
    assert "Measured" in body["detail"]


@pytest.mark.contract
def test_post_remove_returns_409_when_already_removed() -> None:
    """Strict semantics: re-remove raises SubjectCannotRemoveError -> 409."""
    with TestClient(create_app()) as client:
        subject_id = _register_and_mount(client)
        first = client.post(f"/subjects/{subject_id}/remove")
        assert first.status_code == 204
        second = client.post(f"/subjects/{subject_id}/remove")
    assert second.status_code == 409
    body = second.json()
    assert "Removed" in body["detail"]


@pytest.mark.contract
def test_post_remove_rejects_invalid_path_uuid_with_422() -> None:
    """Pydantic UUID parsing on path param."""
    with TestClient(create_app()) as client:
        response = client.post("/subjects/not-a-uuid/remove")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_remove_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        subject_id = _register_and_mount(client)
        response = client.post(
            f"/subjects/{subject_id}/remove",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
