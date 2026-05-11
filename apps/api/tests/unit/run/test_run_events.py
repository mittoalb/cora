"""Unit tests for the Run aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.aggregates.run.events import (
    RunStarted,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Run",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
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
def test_event_type_name_returns_class_name() -> None:
    event = RunStarted(
        run_id=uuid4(),
        name="X",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "RunStarted"


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_subject_to_primitives() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "run_id": str(run_id),
        "name": "32-ID FlyScan",
        "plan_id": str(plan_id),
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_run_started_without_subject_as_null() -> None:
    """Dark-field / calibration runs have subject_id=None — must
    serialize as JSON null (not the string 'None')."""
    run_id = uuid4()
    plan_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="Dark field calibration",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["subject_id"] is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_subject() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "32-ID FlyScan",
            "plan_id": str(plan_id),
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_subject() -> None:
    """JSON null deserializes to Python None for subject_id."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Dark field",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt.subject_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for Run events."""
    original = RunStarted(
        run_id=uuid4(),
        name="X",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunStarted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("PlanDefined", {})
    with pytest.raises(ValueError, match="Unknown RunEvent event_type"):
        from_stored(stored)
