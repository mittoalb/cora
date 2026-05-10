"""Unit tests for the Conduit aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.conduit.events import (
    ConduitDefined,
    event_type_name,
    from_stored,
    to_new_event,
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
        stream_type="Conduit",
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
    event = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ConduitDefined"


@pytest.mark.unit
def test_to_payload_serializes_conduit_defined_to_primitives() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    event = ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "conduit_id": str(conduit_id),
        "name": "Detector-to-Storage",
        "source_zone_id": str(source),
        "target_zone_id": str(target),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_defined() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    stored = _stored(
        "ConduitDefined",
        {
            "conduit_id": str(conduit_id),
            "name": "Detector-to-Storage",
            "source_zone_id": str(source),
            "target_zone_id": str(target),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("ConduitDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ZoneDefined", {})
    with pytest.raises(ValueError, match="Unknown ConduitEvent event_type"):
        from_stored(stored)


@pytest.mark.unit
def test_to_new_event_wraps_domain_event_in_persistence_envelope() -> None:
    conduit_id = uuid4()
    event_id = uuid4()
    correlation_id = uuid4()
    event = ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )

    new_event = to_new_event(
        event,
        event_id=event_id,
        command_name="DefineConduit",
        correlation_id=correlation_id,
    )

    assert new_event.event_id == event_id
    assert new_event.event_type == "ConduitDefined"
    assert new_event.schema_version == 1
    assert new_event.payload == to_payload(event)
    assert new_event.occurred_at == _NOW
    assert new_event.correlation_id == correlation_id
    assert new_event.causation_id is None
    assert new_event.metadata == {"command": "DefineConduit"}


@pytest.mark.unit
def test_to_new_event_propagates_causation_id_when_supplied() -> None:
    correlation = uuid4()
    causation = uuid4()
    event = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )

    new_event = to_new_event(
        event,
        event_id=uuid4(),
        command_name="DefineConduit",
        correlation_id=correlation,
        causation_id=causation,
    )
    assert new_event.causation_id == causation
