"""Contract tests for `POST /assets/{asset_id}/decommission`.

Mirrors `test_remove_subject_endpoint.py`. Covers both source
states of the multi-source-state guard (Commissioned ->
Decommissioned and Active -> Decommissioned) plus the disallowed-
source error mapping.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient, name: str = "APS-2BM") -> str:
    response = client.post(
        "/assets",
        json={"name": name, "level": "Unit", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201
    asset_id: str = response.json()["asset_id"]
    return asset_id


def _register_and_activate(client: TestClient) -> str:
    asset_id = _register_asset(client)
    activated = client.post(f"/assets/{asset_id}/activate")
    assert activated.status_code == 204
    return asset_id


@pytest.mark.contract
def test_post_decommission_returns_204_from_commissioned_state() -> None:
    """Commissioned -> Decommissioned (skipping activate)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/decommission")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_decommission_returns_204_from_active_state() -> None:
    """Full happy path: Active -> Decommissioned."""
    with TestClient(create_app()) as client:
        asset_id = _register_and_activate(client)
        response = client.post(f"/assets/{asset_id}/decommission")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_decommission_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/assets/{missing_id}/decommission")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_decommission_returns_409_when_already_decommissioned() -> None:
    """Strict semantics: re-decommission raises AssetCannotDecommissionError -> 409."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(f"/assets/{asset_id}/decommission")
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/decommission")
    assert second.status_code == 409
    body = second.json()
    assert "Decommissioned" in body["detail"]
    # Multi-source guard: error message lists ALL THREE allowed source
    # states (5e widened from {Commissioned, Active} to also include
    # Maintenance).
    assert "Commissioned" in body["detail"]
    assert "Active" in body["detail"]
    assert "Maintenance" in body["detail"]


@pytest.mark.contract
def test_post_decommission_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/not-a-uuid/decommission")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_decommission_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/decommission",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
