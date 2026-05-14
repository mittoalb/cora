"""E2E smoke: full Run cascade from Capability to Completed.

Keystone e2e: register every upstream aggregate (Capability + Asset
+ Method + Practice + Plan + Subject + mount-target Asset), start a
Run against the chain, complete it, then assert the Completed Run
appears in the projection-backed list endpoint.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_full_run_cascade_to_completed(
    e2e_client: AsyncClient,
    e2e_drain: Callable[[], Awaitable[None]],
) -> None:
    cap = await e2e_client.post("/capabilities", json={"name": "FlyMotion"})
    capability_id = cap.json()["capability_id"]

    method = await e2e_client.post(
        "/methods",
        json={"name": "Test Method", "needs_capabilities": [capability_id]},
    )
    method_id = method.json()["method_id"]

    practice = await e2e_client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    )
    practice_id = practice.json()["practice_id"]

    plan_asset = await e2e_client.post(
        "/assets",
        json={"name": "PlanAsset", "level": "Enterprise", "parent_id": None},
    )
    plan_asset_id = plan_asset.json()["asset_id"]
    add = await e2e_client.post(
        f"/assets/{plan_asset_id}/add_capability",
        json={"capability_id": capability_id},
    )
    assert add.status_code == 204

    plan = await e2e_client.post(
        "/plans",
        json={"name": "32-ID FlyScan", "practice_id": practice_id, "asset_ids": [plan_asset_id]},
    )
    plan_id = plan.json()["plan_id"]

    mount_asset = await e2e_client.post(
        "/assets",
        json={"name": "Goniometer-1", "level": "Unit", "parent_id": str(uuid4())},
    )
    mount_asset_id = mount_asset.json()["asset_id"]
    activated = await e2e_client.post(f"/assets/{mount_asset_id}/activate")
    assert activated.status_code == 204

    subject = await e2e_client.post("/subjects", json={"name": "Sample-A1"})
    subject_id = subject.json()["subject_id"]
    mounted = await e2e_client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    assert mounted.status_code == 204

    started = await e2e_client.post(
        "/runs",
        json={"name": "Run-1", "plan_id": plan_id, "subject_id": subject_id},
    )
    assert started.status_code == 201
    run_id = UUID(started.json()["run_id"])

    completed = await e2e_client.post(f"/runs/{run_id}/complete")
    assert completed.status_code == 204

    await e2e_drain()
    listed = await e2e_client.get("/runs")
    assert listed.status_code == 200
    items = listed.json()["items"]
    matches = [item for item in items if item["run_id"] == str(run_id)]
    assert len(matches) == 1
    assert matches[0]["status"] == "Completed"
