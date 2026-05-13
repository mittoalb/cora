"""Contract tests for `POST /subjects/{subject_id}/store`.

Mirrors `test_return_subject_endpoint.py`.
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


def _register_mount_remove(client: TestClient) -> str:
    subject_id = _register_subject(client)
    asset_id = register_active_asset(client)
    mounted = client.post(f"/subjects/{subject_id}/mount", json={"asset_id": asset_id})
    assert mounted.status_code == 204
    removed = client.post(f"/subjects/{subject_id}/remove")
    assert removed.status_code == 204
    return subject_id


@pytest.mark.contract
def test_post_store_returns_204_on_first_store() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_mount_remove(client)
        response = client.post(f"/subjects/{subject_id}/store")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_store_returns_404_when_subject_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/subjects/{missing_id}/store")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_store_returns_409_when_subject_not_yet_removed() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_id = register_active_asset(client)
        client.post(f"/subjects/{subject_id}/mount", json={"asset_id": asset_id})
        response = client.post(f"/subjects/{subject_id}/store")
    assert response.status_code == 409
    body = response.json()
    assert "Mounted" in body["detail"]
    assert "Removed" in body["detail"]


@pytest.mark.contract
def test_post_store_returns_409_when_already_stored() -> None:
    """Strict semantics: re-store raises SubjectCannotStoreError -> 409."""
    with TestClient(create_app()) as client:
        subject_id = _register_mount_remove(client)
        first = client.post(f"/subjects/{subject_id}/store")
        assert first.status_code == 204
        second = client.post(f"/subjects/{subject_id}/store")
    assert second.status_code == 409
    body = second.json()
    assert "Stored" in body["detail"]
    assert "Removed" in body["detail"]


@pytest.mark.contract
def test_post_store_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/subjects/not-a-uuid/store")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_store_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        subject_id = _register_mount_remove(client)
        response = client.post(
            f"/subjects/{subject_id}/store",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
