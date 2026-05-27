"""HTTP contract tests for the 9 Visit lifecycle endpoints.

Consolidated coverage file: covers `register_visit`, `arrive_visit`,
`start_visit`, `hold_visit`, `resume_visit`, `complete_visit`,
`cancel_visit`, `abort_visit`, `void_visit` per the arch-fitness
substring-match rule. Pins the REST surface: status codes, body
shapes, FSM-walk happy path, 404 / 409 / 400 error mappings.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PLANNED_END = _NOW + timedelta(hours=8)


def _register_visit(client: TestClient) -> str:
    """Register a fresh Visit, return its id. Status starts at Planned."""
    visit_id = str(uuid4())
    response = client.post(
        "/visits",
        json={
            "visit_id": visit_id,
            "policy_id": str(uuid4()),
            "surface_id": str(uuid4()),
            "type": "user",
            "planned_start_at": _NOW.isoformat(),
            "planned_end_at": _PLANNED_END.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["visit_id"] == visit_id
    return visit_id


# ---------------------------------------------------------------------------
# register_visit (POST /visits)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_post_visits_returns_201_with_caller_supplied_id() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
    assert vid


@pytest.mark.contract
def test_post_visits_returns_409_when_visit_id_collides() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        second = client.post(
            "/visits",
            json={
                "visit_id": vid,
                "policy_id": str(uuid4()),
                "surface_id": str(uuid4()),
                "type": "user",
                "planned_start_at": _NOW.isoformat(),
                "planned_end_at": _PLANNED_END.isoformat(),
            },
        )
    assert second.status_code == 409


@pytest.mark.contract
def test_post_visits_returns_400_when_planned_end_not_after_start() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/visits",
            json={
                "visit_id": str(uuid4()),
                "policy_id": str(uuid4()),
                "surface_id": str(uuid4()),
                "type": "user",
                "planned_start_at": _NOW.isoformat(),
                "planned_end_at": _NOW.isoformat(),
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_visits_returns_422_when_type_is_not_in_closed_enum() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/visits",
            json={
                "visit_id": str(uuid4()),
                "policy_id": str(uuid4()),
                "surface_id": str(uuid4()),
                "type": "not-a-real-type",
                "planned_start_at": _NOW.isoformat(),
                "planned_end_at": _PLANNED_END.isoformat(),
            },
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Full lifecycle walk via HTTP: arrive -> start -> hold -> resume -> complete
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_full_lifecycle_walk_returns_204_at_each_step() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        assert client.post(f"/visits/{vid}/arrive").status_code == 204
        assert client.post(f"/visits/{vid}/start").status_code == 204
        assert client.post(f"/visits/{vid}/hold", json={"reason": "beam dump"}).status_code == 204
        assert client.post(f"/visits/{vid}/resume").status_code == 204
        assert client.post(f"/visits/{vid}/complete").status_code == 204


# ---------------------------------------------------------------------------
# 404 on every lifecycle slice when the visit does not exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path_suffix", "body"),
    [
        ("/arrive", None),
        ("/start", None),
        ("/hold", {"reason": "r"}),
        ("/resume", None),
        ("/complete", None),
        ("/cancel", {"reason": "r"}),
        ("/abort", {"reason": "r"}),
        ("/void", {"reason": "r"}),
    ],
)
@pytest.mark.contract
def test_lifecycle_endpoint_returns_404_when_visit_absent(
    path_suffix: str, body: dict[str, str] | None
) -> None:
    with TestClient(create_app()) as client:
        url = f"/visits/{uuid4()}{path_suffix}"
        response = client.post(url, json=body) if body else client.post(url)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 409 on cancel from in-progress (must use abort) -- HL7 v2 A11/A13 split
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cancel_returns_409_when_visit_is_in_progress_must_use_abort() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        client.post(f"/visits/{vid}/arrive")
        client.post(f"/visits/{vid}/start")
        response = client.post(f"/visits/{vid}/cancel", json={"reason": "r"})
    assert response.status_code == 409


@pytest.mark.contract
def test_abort_returns_409_when_visit_is_planned_must_use_cancel() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        response = client.post(f"/visits/{vid}/abort", json={"reason": "r"})
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# 400 on whitespace-only reason for with-reason slices
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_hold_returns_400_on_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        client.post(f"/visits/{vid}/arrive")
        client.post(f"/visits/{vid}/start")
        response = client.post(f"/visits/{vid}/hold", json={"reason": "   "})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 422 on missing required body fields
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_hold_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        client.post(f"/visits/{vid}/arrive")
        client.post(f"/visits/{vid}/start")
        response = client.post(f"/visits/{vid}/hold", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# void terminal: reachable from any non-terminal status
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_void_returns_204_from_planned_status() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        response = client.post(f"/visits/{vid}/void", json={"reason": "BSS duplicate"})
    assert response.status_code == 204


@pytest.mark.contract
def test_void_returns_409_when_visit_is_already_completed() -> None:
    with TestClient(create_app()) as client:
        vid = _register_visit(client)
        client.post(f"/visits/{vid}/arrive")
        client.post(f"/visits/{vid}/start")
        client.post(f"/visits/{vid}/complete")
        response = client.post(f"/visits/{vid}/void", json={"reason": "oops"})
    assert response.status_code == 409
