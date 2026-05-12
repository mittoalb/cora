"""Unit tests for SubjectSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for all 7
Subject lifecycle events. Postgres-side behavior is exercised
in `tests/integration/test_subject_projection_worker_postgres.py`.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.subject.projections import SubjectSummaryProjection

_SUBJECT_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Subject",
        stream_id=_SUBJECT_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = SubjectSummaryProjection()
    assert proj.name == "proj_subject_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "SubjectRegistered",
            "SubjectMounted",
            "SubjectMeasured",
            "SubjectRemoved",
            "SubjectReturned",
            "SubjectStored",
            "SubjectDiscarded",
        }
    )


@pytest.mark.unit
async def test_subject_registered_inserts_with_received_status() -> None:
    proj = SubjectSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "SubjectRegistered",
        {
            "subject_id": str(_SUBJECT_ID),
            "name": "Sample-A",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_subject_summary" in sql
    assert "ON CONFLICT (subject_id) DO NOTHING" in sql
    assert args.args[1] == _SUBJECT_ID
    assert args.args[2] == "Sample-A"
    assert args.args[3] == _NOW


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("SubjectMounted", "Mounted"),
        ("SubjectMeasured", "Measured"),
        ("SubjectRemoved", "Removed"),
        ("SubjectReturned", "Returned"),
        ("SubjectStored", "Stored"),
        ("SubjectDiscarded", "Discarded"),
    ],
)
async def test_lifecycle_transition_updates_status(event_type: str, expected_status: str) -> None:
    """Each transition event writes its status to the projection table.
    Pin: status string matches the SubjectStatus enum exactly (the CHECK
    constraint on the projection table will reject mismatches at
    INSERT time)."""
    proj = SubjectSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {"subject_id": str(_SUBJECT_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_subject_summary" in sql
    assert args.args[1] == _SUBJECT_ID
    assert args.args[2] == expected_status


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    """Belt-and-suspenders: SQL filter prevents this in production but
    the bare match needs `case _: pass` for pyright exhaustiveness on
    str. No execute, no error."""
    proj = SubjectSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})

    await proj.apply(event, conn)

    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_apply_is_idempotent_for_subject_registered() -> None:
    """ON CONFLICT DO NOTHING means re-applying the same event runs
    the same SQL; Postgres handles the duplicate as a no-op."""
    proj = SubjectSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "SubjectRegistered",
        {
            "subject_id": str(_SUBJECT_ID),
            "name": "Sample-A",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    first = conn.execute.await_args_list[0].args
    second = conn.execute.await_args_list[1].args
    assert first == second
