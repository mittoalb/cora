"""Contract tests for `GET /assets/{asset_id}`.

Mirrors `test_get_capability_endpoint.py` / `test_get_subject_endpoint.py`.
Pinned response shape: `{id, name, level, parent_id, lifecycle}`
where `level` and `lifecycle` are the StrEnum string values
(PascalCase per the BC map). `parent_id` is null only for
Enterprise-level roots.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(
    client: TestClient,
    *,
    name: str = "APS-2BM",
    level: str = "Unit",
    parent_id: str | None = None,
) -> UUID:
    body: dict[str, str | None] = {"name": name, "level": level}
    if level == "Enterprise":
        body["parent_id"] = None
    else:
        body["parent_id"] = parent_id if parent_id is not None else str(uuid4())
    response = client.post("/assets", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


@pytest.mark.contract
def test_get_asset_returns_200_with_commissioned_lifecycle_for_new_asset() -> None:
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client, parent_id=parent_id)
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(asset_id),
        "name": "APS-2BM",
        "level": "Unit",
        "parent_id": parent_id,
        "lifecycle": "Commissioned",
    }


@pytest.mark.contract
def test_get_asset_returns_200_with_null_parent_for_enterprise_root() -> None:
    """Pinned: Enterprise-level Assets serialize parent_id as JSON null."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client, name="ANL", level="Enterprise")
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["parent_id"] is None
    assert body["level"] == "Enterprise"


@pytest.mark.contract
def test_get_asset_reflects_lifecycle_after_activate() -> None:
    """Round-trip: register + activate + get → lifecycle=Active."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        activate = client.post(f"/assets/{asset_id}/activate")
        assert activate.status_code == 204
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    assert response.json()["lifecycle"] == "Active"


@pytest.mark.contract
def test_get_asset_reflects_parent_after_relocate() -> None:
    """Round-trip: register + relocate + get → parent_id mutated."""
    new_parent = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        relocate = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": new_parent, "reason": "moved"},
        )
        assert relocate.status_code == 204
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    assert response.json()["parent_id"] == new_parent


@pytest.mark.contract
def test_get_asset_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/assets/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_asset_returns_422_for_malformed_asset_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/assets/not-a-uuid")
    assert response.status_code == 422
