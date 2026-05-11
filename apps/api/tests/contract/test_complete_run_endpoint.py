"""Contract tests for `POST /runs/{run_id}/complete`.

Single-source happy-path terminal: `Running -> Completed`.
Re-completing or completing-from-Aborted raises 409.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _setup_full_run(client: TestClient) -> str:
    """Seed full upstream chain + start a Run. Returns the run_id."""
    cap_id = client.post("/capabilities", json={"name": "FlyMotion"}).json()["capability_id"]
    method_id = client.post("/methods", json={"name": "M", "needs_capabilities": [cap_id]}).json()[
        "method_id"
    ]
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
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    client.post(f"/subjects/{subject_id}/mount")
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_post_complete_run_returns_204_from_running_state() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/complete")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_complete_run_round_trips_into_get_run_response() -> None:
    """End-to-end: complete + get → status=Completed."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/complete")
        response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "Completed"


@pytest.mark.contract
def test_post_complete_run_returns_404_when_run_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/runs/{missing_id}/complete")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_complete_run_returns_409_when_already_completed() -> None:
    """Strict-not-idempotent: re-completing raises 409."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        first = client.post(f"/runs/{run_id}/complete")
        assert first.status_code == 204
        second = client.post(f"/runs/{run_id}/complete")
    assert second.status_code == 409
    body = second.json()
    assert "Running" in body["detail"]


@pytest.mark.contract
def test_post_complete_run_returns_409_when_aborted() -> None:
    """Aborted is terminal — cannot complete from Aborted."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        abort = client.post(f"/runs/{run_id}/abort", json={"reason": "early test abort"})
        assert abort.status_code == 204
        response = client.post(f"/runs/{run_id}/complete")
    assert response.status_code == 409
    assert "Aborted" in response.json()["detail"]


@pytest.mark.contract
def test_post_complete_run_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs/not-a-uuid/complete")
    assert response.status_code == 422
