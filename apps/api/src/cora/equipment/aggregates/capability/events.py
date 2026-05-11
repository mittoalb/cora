"""Domain events emitted by the Capability aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 5a ships `CapabilityDefined`. Subsequent slices add
`CapabilityVersioned` / `CapabilityDeprecated` per the
`Defined → Versioned → Deprecated` lifecycle (deferred per 5a scope).

Status is NOT carried in event payloads — the event type itself
encodes the state change (e.g., `CapabilityVersioned -> status=
VERSIONED`). The evolver hardcodes the mapping per match arm. Same
precedent as `SubjectMounted -> status=MOUNTED` /
`ActorDeactivated -> is_active=False`. See state.py docstring for
the rationale.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class CapabilityDefined:
    """A new technique-class capability was defined.

    Status is implicit (`Defined`) — the evolver sets it.
    """

    capability_id: UUID
    name: str
    occurred_at: datetime


# Discriminated union of every event the Capability aggregate emits.
# Add new event classes above and extend this alias when new slices
# land (5f+: CapabilityVersioned, CapabilityDeprecated).
CapabilityEvent = CapabilityDefined


def event_type_name(event: CapabilityEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CapabilityEvent) -> dict[str, Any]:
    """Serialize a Capability event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case CapabilityDefined(capability_id=capability_id, name=name, occurred_at=occurred_at):
            return {
                "capability_id": str(capability_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> CapabilityEvent:
    """Rebuild a Capability event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "CapabilityDefined":
            return CapabilityDefined(
                capability_id=UUID(payload["capability_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown CapabilityEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "CapabilityDefined",
    "CapabilityEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
