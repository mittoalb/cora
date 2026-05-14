"""Unit tests for RunSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 7
subscribed Run events. Postgres-side behavior is in the integration
suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.projections import RunSummaryProjection

_RUN_ID = uuid4()
_PLAN_ID = uuid4()
_SUBJECT_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 13, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Run",
        stream_id=_RUN_ID,
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
    proj = RunSummaryProjection()
    assert proj.name == "proj_run_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "RunStarted",
            "RunHeld",
            "RunResumed",
            "RunCompleted",
            "RunAborted",
            "RunStopped",
            "RunTruncated",
        }
    )


@pytest.mark.unit
async def test_run_started_inserts_with_running_status_and_genesis_refs() -> None:
    """RunStarted carries plan_id, subject_id (optional), raid (optional)
    in the genesis payload; all surface in the projection at INSERT time."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Tomography-2026-05-13-001",
            "plan_id": str(_PLAN_ID),
            "subject_id": str(_SUBJECT_ID),
            "raid": "https://raid.org/10.7935/test",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_run_summary" in sql
    assert "ON CONFLICT (run_id) DO NOTHING" in sql
    assert "'Running'" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] == "Tomography-2026-05-13-001"
    assert args.args[3] == _PLAN_ID
    assert args.args[4] == _SUBJECT_ID
    assert args.args[5] == "https://raid.org/10.7935/test"
    assert args.args[6] == _NOW
    # 6g-c: parameter_overrides_present defaults FALSE for legacy
    # payloads (no parameter_overrides key in pre-6g-c events).
    assert args.args[7] is False


@pytest.mark.unit
async def test_run_started_with_null_subject_id_for_calibration_run() -> None:
    """Calibration / dark-field Runs have subject_id=None."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "DarkField-cal",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # subject_id
    assert args.args[5] is None  # raid


@pytest.mark.unit
async def test_run_started_sets_parameter_overrides_present_true_when_non_empty() -> None:
    """Phase 6g-c: RunStarted with non-empty parameter_overrides
    payload sets the projection column TRUE."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Run-with-overrides",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "parameter_overrides": {"energy_kev": 12.0},
            "effective_parameters": {"energy_kev": 12.0},
            "triggered_by": "operator:opid:5",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] is True  # parameter_overrides_present


@pytest.mark.unit
async def test_run_started_sets_parameter_overrides_present_false_when_empty() -> None:
    """Phase 6g-c: empty parameter_overrides payload (operator just used
    Plan defaults straight) keeps the projection column FALSE."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Run-no-overrides",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "parameter_overrides": {},
            "effective_parameters": {"energy_kev": 12.0},
            "triggered_by": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("RunHeld", "Held"),
        ("RunResumed", "Running"),
        ("RunCompleted", "Completed"),
        ("RunAborted", "Aborted"),
        ("RunStopped", "Stopped"),
        ("RunTruncated", "Truncated"),
    ],
)
async def test_lifecycle_transition_updates_status(event_type: str, expected_status: str) -> None:
    """Each lifecycle event writes its expected status. Note that
    RunResumed flips back to 'Running' (collapsing the held->resumed
    round-trip into a single 'Running' state in the projection)."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_run_summary" in sql
    assert "SET status = $2" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] == expected_status


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
