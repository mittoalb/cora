"""Domain events emitted by the Zone aggregate, plus the discriminated union.

Mirrors `cora/access/aggregates/actor/events.py` exactly in shape (the
per-aggregate events module is the locked cross-BC pattern: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`, `to_new_event`). The `to_new_event` body is byte-
identical across BCs today; cross-BC extraction is gated on a third
consumer per Rule of Three (with idempotency + observability already
extracted, this is the next candidate when Phase 3b lands).

Per the locked "primitives in events" convention, payloads serialize
to plain dicts of primitives; the evolver re-validates on read by
reconstructing value objects.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports import NewEvent
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ZoneDefined:
    """A new Trust zone was defined."""

    zone_id: UUID
    name: str
    occurred_at: datetime


# Discriminated union of every event the Zone aggregate emits. Add new
# event classes above and extend this alias when new slices land.
ZoneEvent = ZoneDefined


def event_type_name(event: ZoneEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ZoneEvent) -> dict[str, Any]:
    """Serialize a Zone event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    The evolver re-validates by reconstructing value objects on the read
    path; this round-trip is the safety net for schema evolution.
    """
    match event:
        case ZoneDefined(zone_id=zone_id, name=name, occurred_at=occurred_at):
            return {
                "zone_id": str(zone_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ZoneEvent:
    """Rebuild a Zone event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "ZoneDefined":
            return ZoneDefined(
                zone_id=UUID(payload["zone_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown ZoneEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


def to_new_event(
    event: ZoneEvent,
    *,
    event_id: UUID,
    command_name: str,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> NewEvent:
    """Wrap a domain event in the persistence envelope.

    Identical body to `cora.access.aggregates.actor.events.to_new_event`
    today; both will get hoisted to a cross-BC helper once a third
    aggregate lands (Rule of Three). For now the per-aggregate copy
    keeps each aggregate's events module self-contained.
    """
    return NewEvent(
        event_id=event_id,
        event_type=event_type_name(event),
        schema_version=1,
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
        metadata={"command": command_name},
    )


__all__ = [
    "ZoneDefined",
    "ZoneEvent",
    "event_type_name",
    "from_stored",
    "to_new_event",
    "to_payload",
]
