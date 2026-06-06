"""Unit tests for `VisitSummaryProjection`.

Pins per-event-type apply() dispatch + idempotency. Postgres-side
behavior is exercised in the integration-tier projection-worker tests.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.projections import VisitSummaryProjection

_VID = UUID("01900000-0000-7000-8000-00000000d001")
_PID = UUID("01900000-0000-7000-8000-00000000d002")
_SID = UUID("01900000-0000-7000-8000-00000000d003")
_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Visit",
        stream_id=_VID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = VisitSummaryProjection()
    assert proj.name == "proj_trust_visit_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "VisitRegistered",
            "VisitArrived",
            "VisitStarted",
            "VisitHeld",
            "VisitResumed",
            "VisitCompleted",
            "VisitCancelled",
            "VisitAborted",
            "VisitVoided",
        }
    )


@pytest.mark.unit
async def test_apply_skips_unsubscribed_event_type() -> None:
    """Defensive: an event the projection didn't subscribe to is a no-op."""
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    event = _stored("SomeOtherEvent", {"visit_id": str(_VID), "occurred_at": _NOW.isoformat()})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_visit_registered_inserts_full_row() -> None:
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitRegistered",
        {
            "visit_id": str(_VID),
            "policy_id": str(_PID),
            "surface_id": str(_SID),
            "type": "user",
            "planned_start_at": _NOW.isoformat(),
            "planned_end_at": (_NOW + timedelta(hours=4)).isoformat(),
            "occurred_at": _NOW.isoformat(),
            "parent_id": None,
            "external_refs": [],
        },
    )
    await proj.apply(event, conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    assert "INSERT INTO proj_trust_visit_summary" in args.args[0]
    assert "ON CONFLICT (visit_id) DO NOTHING" in args.args[0]
    assert args.args[1] == _VID
    assert args.args[2] == _PID
    assert args.args[3] == _SID
    assert args.args[4] == "user"


@pytest.mark.parametrize(
    ("event_type", "status_expected", "sql_fragment"),
    [
        ("VisitArrived", "Arrived", "arrived_at = $2"),
        ("VisitStarted", "InProgress", "started_at = $2"),
        ("VisitResumed", "InProgress", "status = 'InProgress'"),
    ],
)
@pytest.mark.unit
async def test_simple_lifecycle_events_update_status(
    event_type: str, status_expected: str, sql_fragment: str
) -> None:
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {"visit_id": str(_VID), "occurred_at": _NOW.isoformat()},
    )
    await proj.apply(event, conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql: str = args.args[0]
    assert status_expected in sql
    assert sql_fragment in sql


@pytest.mark.unit
async def test_visit_held_updates_status_and_reason() -> None:
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitHeld",
        {"visit_id": str(_VID), "reason": "beam dump", "occurred_at": _NOW.isoformat()},
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert "OnHold" in args.args[0]
    assert "last_status_reason" in args.args[0]
    assert args.args[2] == "beam dump"


@pytest.mark.unit
async def test_visit_completed_updates_completed_at_and_terminal_status() -> None:
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitCompleted",
        {"visit_id": str(_VID), "occurred_at": _NOW.isoformat()},
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert "completed_at = $2" in args.args[0]
    assert "Completed" in args.args[0]


@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("VisitCancelled", "Cancelled"),
        ("VisitAborted", "Aborted"),
        ("VisitVoided", "Voided"),
    ],
)
@pytest.mark.unit
async def test_terminal_with_reason_events_record_status_and_reason(
    event_type: str, expected_status: str
) -> None:
    """Cancel / Abort / Void share the terminal-status + completed_at + reason
    shape; the projection's _UPDATE_TERMINAL_WITH_REASON_SQL is reused for
    all three with the status as $2."""
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {"visit_id": str(_VID), "reason": "test reason", "occurred_at": _NOW.isoformat()},
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert "completed_at = $3" in args.args[0]
    assert "last_status_reason = $4" in args.args[0]
    # Args: [sql, visit_id, status, completed_at, reason]
    assert args.args[1] == _VID
    assert args.args[2] == expected_status
    assert args.args[4] == "test reason"


@pytest.mark.unit
async def test_visit_registered_handles_part_of_and_external_refs() -> None:
    proj = VisitSummaryProjection()
    conn = AsyncMock()
    parent = uuid4()
    event = _stored(
        "VisitRegistered",
        {
            "visit_id": str(_VID),
            "policy_id": str(_PID),
            "surface_id": str(_SID),
            "type": "commissioning",
            "planned_start_at": _NOW.isoformat(),
            "planned_end_at": (_NOW + timedelta(hours=1)).isoformat(),
            "occurred_at": _NOW.isoformat(),
            "parent_id": str(parent),
            "external_refs": [{"scheme": "proposal", "value": "12345"}],
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    # Args: sql, visit_id, policy_id, surface_id, type, planned_start, planned_end,
    #       parent_id, external_refs_json, occurred_at
    assert args.args[7] == parent
    assert '[{"scheme": "proposal", "value": "12345"}]' in args.args[8]
