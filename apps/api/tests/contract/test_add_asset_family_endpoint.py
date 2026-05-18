"""Contract tests for `POST /assets/{asset_id}/add_capability`.

Action endpoint with body `{family_id}`. Mirrors the relocate
endpoint contract (also two-id action endpoint) but for capability
mutation. Pinned: get_asset reflects the new capability after add.
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


@pytest.mark.contract
def test_post_add_capability_returns_204_on_happy_path() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add_capability",
            json={"family_id": cap},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_add_capability_round_trips_into_get_asset_response() -> None:
    """End-to-end: add_capability + get_asset → capability appears in
    the response's capabilities list."""
    cap1 = str(uuid4())
    cap2 = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap1})
        client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap2})
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    body = response.json()
    # Sorted by UUID string form (deterministic).
    assert body["families"] == sorted([cap1, cap2])


@pytest.mark.contract
def test_post_add_capability_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/add_capability",
            json={"family_id": str(uuid4())},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_capability_returns_409_when_capability_already_present() -> None:
    """Strict-not-idempotent: re-adding raises 409."""
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap})
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap})
    assert second.status_code == 409
    assert "already" in second.json()["detail"]


@pytest.mark.contract
def test_post_add_capability_returns_409_when_asset_is_decommissioned() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap})
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.contract
def test_post_add_capability_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/not-a-uuid/add_capability",
            json={"family_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_capability_rejects_missing_family_id_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/add_capability", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_capability_rejects_non_uuid_capability_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add_capability",
            json={"family_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_capability_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add_capability",
            json={"family_id": str(uuid4())},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
