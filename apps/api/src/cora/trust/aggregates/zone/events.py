"""Domain events emitted by the Zone aggregate, plus the discriminated union.

Mirrors `cora/access/aggregates/actor/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`; handlers
call it with `event_type=event_type_name(event)` and
`payload=to_payload(event)`.

Per the locked "primitives in events" convention, payloads serialize
to plain dicts of primitives; the evolver re-validates on read by
reconstructing value objects.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

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


__all__ = [
    "ZoneDefined",
    "ZoneEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
