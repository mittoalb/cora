"""Contract tests for `POST /subjects/{subject_id}/measure`.

Mirrors `test_mount_subject_endpoint.py`. Each test registers + mounts
a subject via the existing endpoints, then exercises the measure
transition + its error mappings.
"""

from uuid import UUID, uuid4

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


@pytest.mark.contract
def test_post_measure_returns_204_on_first_measure() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_and_mount(client)
        response = client.post(f"/subjects/{subject_id}/measure")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_measure_returns_404_when_subject_does_not_exist() -> None:
    """SubjectNotFoundError -> 404 via the BC's exception handler."""
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/subjects/{missing_id}/measure")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_measure_returns_409_when_subject_only_received() -> None:
    """SubjectCannotMeasureError on Received subject -> 409 via the
    shared `_handle_subject_cannot_transition` handler."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post(f"/subjects/{subject_id}/measure")
    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert "Received" in body["detail"]
    assert "Mounted" in body["detail"]


@pytest.mark.contract
def test_post_measure_returns_409_when_already_measured() -> None:
    """Strict semantics: re-measure raises SubjectCannotMeasureError -> 409."""
    with TestClient(create_app()) as client:
        subject_id = _register_and_mount(client)
        first = client.post(f"/subjects/{subject_id}/measure")
        assert first.status_code == 204
        second = client.post(f"/subjects/{subject_id}/measure")
    assert second.status_code == 409
    body = second.json()
    assert "Measured" in body["detail"]
    assert "Mounted" in body["detail"]


@pytest.mark.contract
def test_post_measure_rejects_invalid_path_uuid_with_422() -> None:
    """Pydantic UUID parsing on path param."""
    with TestClient(create_app()) as client:
        response = client.post("/subjects/not-a-uuid/measure")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_measure_with_x_principal_id_header_succeeds() -> None:
    """Pin: the X-Principal-Id header flows through update-style routes
    just like create-style. Fallback to SYSTEM_PRINCIPAL_ID when absent
    (covered by other tests in this file)."""
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        subject_id = _register_and_mount(client)
        response = client.post(
            f"/subjects/{subject_id}/measure",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_subject_response_uuid_is_parseable() -> None:
    """Defensive cross-check that the registration response yields a parseable UUID."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
    UUID(subject_id)
