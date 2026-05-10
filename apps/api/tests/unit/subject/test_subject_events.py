"""Unit tests for the Subject aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.subject.aggregates.subject.events import (
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell — only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Subject",
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
    event = SubjectRegistered(subject_id=uuid4(), name="Sample-A1", occurred_at=_NOW)
    assert event_type_name(event) == "SubjectRegistered"


@pytest.mark.unit
def test_to_payload_serializes_subject_registered_to_primitives() -> None:
    subject_id = uuid4()
    event = SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "name": "Sample-A1",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_subject_registered() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectRegistered",
        {
            "subject_id": str(subject_id),
            "name": "Sample-A1",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = SubjectRegistered(subject_id=uuid4(), name="Sample-A1", occurred_at=_NOW)
    stored = _stored("SubjectRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown SubjectEvent event_type"):
        from_stored(stored)


# ---------- SubjectMounted ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_mounted_class_name() -> None:
    event = SubjectMounted(subject_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "SubjectMounted"


@pytest.mark.unit
def test_to_payload_serializes_subject_mounted_to_primitives() -> None:
    """Status NOT in payload — event type encodes the state change.
    Pinned because adding `status` to the payload (e.g., to support
    a generic 'set status' command later) is an additive change that
    must be deliberate."""
    subject_id = uuid4()
    event = SubjectMounted(subject_id=subject_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_mounted() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectMounted",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectMounted(subject_id=subject_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_mounted() -> None:
    original = SubjectMounted(subject_id=uuid4(), occurred_at=_NOW)
    stored = _stored("SubjectMounted", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectMeasured ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_measured_class_name() -> None:
    event = SubjectMeasured(subject_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "SubjectMeasured"


@pytest.mark.unit
def test_to_payload_serializes_subject_measured_to_primitives() -> None:
    """Status NOT in payload (event type encodes the state change). Same
    convention as SubjectMounted; pinned per-event-class so an additive
    payload field on Measured is a deliberate change."""
    subject_id = uuid4()
    event = SubjectMeasured(subject_id=subject_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_measured() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectMeasured",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectMeasured(subject_id=subject_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_measured() -> None:
    original = SubjectMeasured(subject_id=uuid4(), occurred_at=_NOW)
    stored = _stored("SubjectMeasured", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectRemoved ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_removed_class_name() -> None:
    event = SubjectRemoved(subject_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "SubjectRemoved"


@pytest.mark.unit
def test_to_payload_serializes_subject_removed_to_primitives() -> None:
    """Status NOT in payload — multi-source-to-single-target transitions
    are still encoded by event TYPE alone. The decider's source-state
    guard is what enforces Mounted | Measured at command time; the
    event itself doesn't need to record where it came from."""
    subject_id = uuid4()
    event = SubjectRemoved(subject_id=subject_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in to_payload(event)
    assert "from_status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_removed() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectRemoved",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectRemoved(subject_id=subject_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_removed() -> None:
    original = SubjectRemoved(subject_id=uuid4(), occurred_at=_NOW)
    stored = _stored("SubjectRemoved", to_payload(original))
    assert from_stored(stored) == original


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`.
