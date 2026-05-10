"""Domain events emitted by the Conduit aggregate, plus the discriminated union.

Mirrors `cora/trust/aggregates/zone/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ConduitDefined:
    """A new Trust conduit was defined between two zones."""

    conduit_id: UUID
    name: str
    source_zone_id: UUID
    target_zone_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Conduit aggregate emits.
ConduitEvent = ConduitDefined


def event_type_name(event: ConduitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ConduitEvent) -> dict[str, Any]:
    """Serialize a Conduit event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case ConduitDefined(
            conduit_id=conduit_id,
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "name": name,
                "source_zone_id": str(source_zone_id),
                "target_zone_id": str(target_zone_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ConduitEvent:
    """Rebuild a Conduit event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "ConduitDefined":
            return ConduitDefined(
                conduit_id=UUID(payload["conduit_id"]),
                name=payload["name"],
                source_zone_id=UUID(payload["source_zone_id"]),
                target_zone_id=UUID(payload["target_zone_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown ConduitEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ConduitDefined",
    "ConduitEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
