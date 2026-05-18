"""Contract tests for `GET /plans/{plan_id}`.

Mirrors `test_get_practice_endpoint.py`. Pinned response shape:
`{id, name, practice_id, asset_ids, status}` where `asset_ids` is
a sorted list of UUID strings (deterministic ordering for client
diffs and cache validation).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _setup_full_plan(client: TestClient) -> tuple[str, str, str]:
    """Seed all upstream then create a Plan. Returns (plan_id, practice_id, asset_id)."""
    cap_id = client.post("/families", json={"name": "FlyMotion"}).json()["family_id"]
    method_id = client.post(
        "/methods", json={"name": "Test Method", "needed_families": [cap_id]}
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "TestAsset", "level": "Enterprise", "parent_id": None},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={
            "name": "32-ID FlyScan",
            "practice_id": practice_id,
            "asset_ids": [asset_id],
        },
    ).json()["plan_id"]
    return plan_id, practice_id, asset_id


@pytest.mark.contract
def test_get_plan_returns_200_with_defined_status_for_new_plan() -> None:
    with TestClient(create_app()) as client:
        plan_id, practice_id, asset_id = _setup_full_plan(client)
        response = client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": plan_id,
        "name": "32-ID FlyScan",
        "practice_id": practice_id,
        "asset_ids": [asset_id],
        "status": "Defined",
        # Null until version_plan runs (6e-2).
        "version": None,
    }


@pytest.mark.contract
def test_get_plan_returns_sorted_asset_ids_for_deterministic_response() -> None:
    """Multi-asset binding: response asset_ids are deterministically
    ordered for client diff stability."""
    with TestClient(create_app()) as client:
        cap_id = client.post("/families", json={"name": "FlyMotion"}).json()["family_id"]
        method_id = client.post(
            "/methods",
            json={"name": "Test Method", "needed_families": [cap_id]},
        ).json()["method_id"]
        practice_id = client.post(
            "/practices",
            json={
                "name": "Test Practice",
                "method_id": method_id,
                "site_id": str(uuid4()),
            },
        ).json()["practice_id"]
        # Three Assets, all with the needed capability.
        asset_ids: list[str] = []
        for i in range(3):
            asset_id = client.post(
                "/assets",
                json={"name": f"Asset{i}", "level": "Enterprise", "parent_id": None},
            ).json()["asset_id"]
            client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap_id})
            asset_ids.append(asset_id)
        plan_id = client.post(
            "/plans",
            json={"name": "X", "practice_id": practice_id, "asset_ids": asset_ids},
        ).json()["plan_id"]

        response = client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_ids"] == sorted(asset_ids)


@pytest.mark.contract
def test_get_plan_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/plans/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_plan_returns_422_for_malformed_plan_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/plans/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_plan_omits_audit_snapshots_from_response_per_slim_aggregate() -> None:
    """gate-review Q4: `method_id` and the snapshots live in the
    PlanDefined event payload but NOT in get_plan's response.
    Bind-time audit data is accessible via a future audit query
    (deferred 6e-3+), not the current-state get."""
    with TestClient(create_app()) as client:
        plan_id, _, _ = _setup_full_plan(client)
        response = client.get(f"/plans/{plan_id}")

    body = response.json()
    assert "method_id" not in body
    assert "method_needed_families_snapshot" not in body
    assert "asset_families_snapshot" not in body
