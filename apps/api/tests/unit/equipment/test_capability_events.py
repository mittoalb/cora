"""Unit tests for the Capability aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

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
        stream_type="Capability",
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
    event = CapabilityDefined(capability_id=uuid4(), name="Tomography", occurred_at=_NOW)
    assert event_type_name(event) == "CapabilityDefined"


@pytest.mark.unit
def test_to_payload_serializes_capability_defined_to_primitives() -> None:
    capability_id = uuid4()
    event = CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW)
    assert to_payload(event) == {
        "capability_id": str(capability_id),
        "name": "Tomography",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_defined() -> None:
    capability_id = uuid4()
    stored = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(capability_id),
            "name": "Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == CapabilityDefined(
        capability_id=capability_id, name="Tomography", occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = CapabilityDefined(capability_id=uuid4(), name="Tomography", occurred_at=_NOW)
    stored = _stored("CapabilityDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown CapabilityEvent event_type"):
        from_stored(stored)
