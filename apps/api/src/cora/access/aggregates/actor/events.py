"""Domain events emitted by the Actor aggregate, plus the discriminated union.

Events live in the aggregate folder (not the slice) because they are
intrinsic facts about the aggregate's history — the slice just decides
when to emit them. The evolver dispatches on the union; new event types
are appended both as a class definition and to the union alias.

Per the locked "primitives in events" convention, payloads serialize
to plain dicts of primitives. `to_payload` and `from_stored` are the
single home for the (de)serialization logic; per-slice handlers no
longer carry their own serializers.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ActorRegistered:
    """A new actor was registered."""

    actor_id: UUID
    name: str
    occurred_at: datetime


# Discriminated union of every event the Actor aggregate emits. Add new
# event classes above and extend this alias when new slices land.
ActorEvent = ActorRegistered


def event_type_name(event: ActorEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ActorEvent) -> dict[str, Any]:
    """Serialize an Actor event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    The evolver re-validates by reconstructing value objects on the read
    path; this round-trip is the safety net for schema evolution.
    """
    match event:
        case ActorRegistered(actor_id=actor_id, name=name, occurred_at=occurred_at):
            return {
                "actor_id": str(actor_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ActorEvent:
    """Rebuild an Actor event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "ActorRegistered":
            return ActorRegistered(
                actor_id=UUID(payload["actor_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown ActorEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ActorEvent",
    "ActorRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
