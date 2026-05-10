"""Unit tests for the Actor aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor.events import (
    ActorRegistered,
    event_type_name,
    from_stored,
    to_new_event,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


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
        stream_type="Actor",
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
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)
    assert event_type_name(event) == "ActorRegistered"


@pytest.mark.unit
def test_to_payload_serializes_actor_registered_to_primitives() -> None:
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)
    assert to_payload(event) == {
        "actor_id": str(actor_id),
        "name": "Doga",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_actor_registered() -> None:
    actor_id = uuid4()
    stored = _stored(
        "ActorRegistered",
        {
            "actor_id": str(actor_id),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    actor_id = uuid4()
    original = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)
    stored = _stored("ActorRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("SomethingElse", {})
    with pytest.raises(ValueError, match="Unknown ActorEvent event_type"):
        from_stored(stored)


@pytest.mark.unit
def test_to_new_event_wraps_domain_event_in_persistence_envelope() -> None:
    """Cross-BC envelope: discriminator + payload from the centralized
    helpers, plus per-call event_id + command_name + correlation_id."""
    actor_id = uuid4()
    event_id = uuid4()
    correlation_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)

    new_event = to_new_event(
        event,
        event_id=event_id,
        command_name="RegisterActor",
        correlation_id=correlation_id,
    )

    assert new_event.event_id == event_id
    assert new_event.event_type == "ActorRegistered"
    assert new_event.schema_version == 1
    assert new_event.payload == to_payload(event)
    assert new_event.occurred_at == _NOW
    assert new_event.correlation_id == correlation_id
    assert new_event.causation_id is None
    assert new_event.metadata == {"command": "RegisterActor"}


@pytest.mark.unit
def test_to_new_event_propagates_causation_id_when_supplied() -> None:
    actor_id = uuid4()
    correlation = uuid4()
    causation = uuid4()
    event = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)

    new_event = to_new_event(
        event,
        event_id=uuid4(),
        command_name="RegisterActor",
        correlation_id=correlation,
        causation_id=causation,
    )
    assert new_event.causation_id == causation
