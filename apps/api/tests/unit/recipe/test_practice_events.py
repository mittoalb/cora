"""Unit tests for the Practice aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.practice.events import (
    PracticeDefined,
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
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Practice",
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
    event = PracticeDefined(
        practice_id=uuid4(),
        name="X",
        method_id=uuid4(),
        site_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PracticeDefined"


@pytest.mark.unit
def test_to_payload_serializes_practice_defined_to_primitives() -> None:
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    event = PracticeDefined(
        practice_id=practice_id,
        name="APS Sector 2 XRF Fly Mapping",
        method_id=method_id,
        site_id=site_id,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "practice_id": str(practice_id),
        "name": "APS Sector 2 XRF Fly Mapping",
        "method_id": str(method_id),
        "site_id": str(site_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_practice_defined() -> None:
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    stored = _stored(
        "PracticeDefined",
        {
            "practice_id": str(practice_id),
            "name": "APS Standard Tomography",
            "method_id": str(method_id),
            "site_id": str(site_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PracticeDefined(
        practice_id=practice_id,
        name="APS Standard Tomography",
        method_id=method_id,
        site_id=site_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net."""
    original = PracticeDefined(
        practice_id=uuid4(),
        name="X",
        method_id=uuid4(),
        site_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("PracticeDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("MethodDefined", {})
    with pytest.raises(ValueError, match="Unknown PracticeEvent event_type"):
        from_stored(stored)
