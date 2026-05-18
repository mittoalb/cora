"""Contract tests for `POST /runs` wire-level (Phase 6i-c).

Pins the wire-level Campaign membership behavior introduced in 6i-c:

  - happy path: POST /runs with campaign_id returns 201 and
    RunStarted carries the campaign_id on the persisted payload
    (asserted via direct event-store inspection; the RunResponse
    DTO does not surface campaign_id today).
  - 404 path: POST /runs with a campaign_id for a Campaign that
    does not exist (decider's load returns None -> handler raises
    CampaignNotFoundError -> Run BC's exception handler maps to
    HTTP 404).
  - 409 path: POST /runs with a campaign_id for a Campaign in a
    terminal status (Closed) raises RunCannotJoinCampaignError ->
    HTTP 409.

The full upstream chain (Family + Asset + Method + Practice +
Plan + Subject) is set up via the public HTTP API per the existing
`_setup_chain` pattern in test_start_run_idempotency.py.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._subject_helpers import register_active_asset


def _setup_chain(client: TestClient) -> tuple[str, str]:
    cap_id = client.post("/families", json={"name": "FlyMotion"}).json()["family_id"]
    method_id = client.post("/methods", json={"name": "M", "needed_families": [cap_id]}).json()[
        "method_id"
    ]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets", json={"name": "A", "level": "Enterprise", "parent_id": None}
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    return plan_id, subject_id


def _register_campaign(client: TestClient, *, intent: str = "Series") -> str:
    response = client.post(
        "/campaigns",
        json={"name": "campaign-for-start-run", "intent": intent, "lead_actor_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    cid: str = response.json()["campaign_id"]
    return cid


def _load_run_payload(app: FastAPI, run_id: UUID) -> dict[str, object]:
    """Load the RunStarted payload directly from the in-memory event store.

    The `RunResponse` DTO returned by `GET /runs/{run_id}` does not
    expose `campaign_id` today, so we drop down to the event store
    to inspect the persisted RunStarted event. Same pattern used by
    the membership endpoint tests.
    """
    events, _ = asyncio.run(app.state.deps.event_store.load("Run", run_id))
    assert events, "expected at least one Run event"
    return dict(events[0].payload)


@pytest.mark.contract
def test_post_runs_with_campaign_id_returns_201() -> None:
    """Happy path: POST /runs with a non-terminal Campaign returns 201
    and the persisted RunStarted carries the campaign_id."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id = _setup_chain(client)
        cid = _register_campaign(client)
        # Move Campaign to Active so the start_run path exercises the
        # Active branch as well as Planned (both eligible).
        client.post(f"/campaigns/{cid}/start")
        response = client.post(
            "/runs",
            json={
                "name": "campaign-bound-run",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "campaign_id": cid,
            },
        )
        assert response.status_code == 201, response.text
        run_id = UUID(response.json()["run_id"])

        payload = _load_run_payload(app, run_id)
        assert payload["campaign_id"] == cid


@pytest.mark.contract
def test_post_runs_returns_404_when_campaign_not_found() -> None:
    """POST /runs with a random campaign_id raises CampaignNotFoundError
    in the handler's pre-load step, mapped to HTTP 404 via Run BC's
    exception handler registration."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        bogus_campaign_id = str(uuid4())
        response = client.post(
            "/runs",
            json={
                "name": "ghost-campaign-run",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "campaign_id": bogus_campaign_id,
            },
        )
    assert response.status_code == 404, response.text
    assert "campaign" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_runs_returns_409_when_campaign_terminal() -> None:
    """POST /runs with a campaign_id for a Closed Campaign raises
    RunCannotJoinCampaignError -> HTTP 409."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        cid = _register_campaign(client)
        client.post(f"/campaigns/{cid}/start")  # Planned -> Active
        client.post(f"/campaigns/{cid}/close")  # Active -> Closed
        response = client.post(
            "/runs",
            json={
                "name": "terminal-campaign-run",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "campaign_id": cid,
            },
        )
    assert response.status_code == 409, response.text
    assert "campaign" in response.json()["detail"].lower()
