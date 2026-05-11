"""Contract tests for `POST /capabilities/{capability_id}/version`.

Action endpoint with body `{version_tag}`. Multi-source guard
(Defined | Versioned -> Versioned).
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
def test_post_version_capability_returns_204_from_defined_state() -> None:
    """First revision (Defined → Versioned)."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/version",
            json={"version_tag": "v2"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_version_capability_returns_204_from_versioned_state() -> None:
    """Subsequent revision (Versioned → Versioned)."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        first = client.post(f"/capabilities/{capability_id}/version", json={"version_tag": "v1"})
        assert first.status_code == 204
        second = client.post(f"/capabilities/{capability_id}/version", json={"version_tag": "v2"})
    assert second.status_code == 204


@pytest.mark.contract
def test_post_version_capability_round_trips_into_get_capability_response() -> None:
    """End-to-end: version + get → status=Versioned, version=label."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        client.post(
            f"/capabilities/{capability_id}/version",
            json={"version_tag": "2026-Q3"},
        )
        response = client.get(f"/capabilities/{capability_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "2026-Q3"


@pytest.mark.contract
def test_post_version_capability_returns_404_when_capability_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/capabilities/{missing_id}/version", json={"version_tag": "v1"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_capability_returns_409_when_deprecated() -> None:
    """Deprecated capabilities cannot be re-versioned."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        deprecate = client.post(f"/capabilities/{capability_id}/deprecate")
        assert deprecate.status_code == 204
        response = client.post(f"/capabilities/{capability_id}/version", json={"version_tag": "v2"})
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_version_capability_rejects_empty_version_tag_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(f"/capabilities/{capability_id}/version", json={"version_tag": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_capability_rejects_whitespace_only_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/version",
            json={"version_tag": "   "},
        )
    assert response.status_code == 400
    assert "version tag" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_version_capability_rejects_too_long_with_422() -> None:
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/version",
            json={"version_tag": "v" * 51},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_capability_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/capabilities/not-a-uuid/version", json={"version_tag": "v1"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_capability_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/version",
            json={"version_tag": "v1"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
