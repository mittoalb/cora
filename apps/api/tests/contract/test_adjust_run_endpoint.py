"""Contract tests for `POST /runs/{run_id}/adjust` (Phase 6j).

Multi-source mid-flight steering: `Running | Held -> Running | Held`
(status preserved). Body carries `parameter_patch` (RFC 7396 merge
patch), `reason` (1-500 chars), optional `decided_by_decision_id`.
Returns 204 on success. Adjust on terminal Runs raises 409.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._subject_helpers import register_active_asset

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy_kev": {"type": "number", "minimum": 5, "maximum": 50},
            "exposure_ms": {"type": "integer", "minimum": 1},
        },
    }


def _setup_full_run(
    client: TestClient,
    *,
    method_schema: dict[str, Any] | None = None,
    plan_defaults: dict[str, Any] | None = None,
) -> str:
    """Seed full upstream chain + start a Run. Returns the run_id."""
    cap_id = client.post("/capabilities", json={"name": "FlyMotion"}).json()["capability_id"]
    method_id = client.post("/methods", json={"name": "M", "needed_capabilities": [cap_id]}).json()[
        "method_id"
    ]
    if method_schema is not None:
        r = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": method_schema},
        )
        assert r.status_code == 204, r.text
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets", json={"name": "A", "level": "Enterprise", "parent_id": None}
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add_capability", json={"capability_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    if plan_defaults:
        r2 = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": plan_defaults},
        )
        assert r2.status_code == 204, r2.text
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_post_adjust_run_returns_204_happy_path() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameter_patch": {"energy_kev": 12.0},
                "reason": "re-center on ROI",
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_adjust_run_returns_204_with_decision_id_link() -> None:
    """Optional decided_by_decision_id flows through on the payload
    (no existence check at the write path)."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameter_patch": {"energy_kev": 13.0},
                "reason": "agent steering",
                "decided_by_decision_id": str(uuid4()),
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_adjust_run_returns_204_from_held_state() -> None:
    """Multi-source guard accepts Held."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        client.post(f"/runs/{run_id}/hold")
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameter_patch": {"energy_kev": 14.0},
                "reason": "tune during pause",
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_adjust_run_returns_404_when_run_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/runs/{missing_id}/adjust",
            json={"parameter_patch": {"x": 1}, "reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
@pytest.mark.parametrize(
    ("transition", "expected_status"),
    [
        ("complete", "Completed"),
        ("abort", "Aborted"),
        ("stop", "Stopped"),
        ("truncate", "Truncated"),
    ],
)
def test_post_adjust_run_returns_409_for_each_terminal_state(
    transition: str, expected_status: str
) -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        if transition == "complete":
            client.post(f"/runs/{run_id}/complete")
        else:
            client.post(f"/runs/{run_id}/{transition}", json={"reason": "test"})

        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy_kev": 12.0}, "reason": "late adjust"},
        )
    assert response.status_code == 409, response.text
    assert expected_status in response.json()["detail"]


@pytest.mark.contract
def test_post_adjust_run_returns_400_for_empty_patch() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {}, "reason": "x"},
        )
    assert response.status_code == 400, response.text
    assert "at least one change" in response.json()["detail"]


@pytest.mark.contract
def test_post_adjust_run_returns_400_for_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy_kev": 12.0}, "reason": "   "},
        )
    assert response.status_code == 400, response.text
    assert "adjust reason" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_adjust_run_returns_400_when_merged_violates_schema() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameter_patch": {"energy_kev": 1.0},  # below minimum=5
                "reason": "x",
            },
        )
    assert response.status_code == 400, response.text
    assert "adjustment" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_adjust_run_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy_kev": 12.0}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_returns_422_when_patch_missing() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy_kev": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/runs/not-a-uuid/adjust",
            json={"parameter_patch": {"x": 1}, "reason": "x"},
        )
    assert response.status_code == 422
