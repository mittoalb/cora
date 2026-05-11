"""Domain events emitted by the Practice aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 6d-1 ships `PracticeDefined`. Phase 6d-2 adds
`PracticeVersioned` and `PracticeDeprecated` per the
`Defined → Versioned → Deprecated` lifecycle. Mirrors Method's
transition shape (Recipe 6b) and Capability's (Equipment 5f-2).

## Payload conventions

`method_id` and `site_id` carry as primitive UUIDs in the payload.
Eventual-consistency stance: existence is NOT verified at decide
time (mismatch surfaces at Plan binding in 6e).

Status is NOT carried in event payloads — the event type itself
encodes the state change. The evolver hardcodes the mapping per
match arm. Same precedent as MethodDefined / CapabilityDefined /
SubjectMounted / ActorDeactivated.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class PracticeDefined:
    """A new facility-adapted Method (Practice) was defined.

    Status is implicit (`Defined`) — the evolver sets it.
    `method_id` is the Method this Practice adapts; `site_id` is the
    Site-level Asset this Practice belongs to. Both eventual-
    consistency refs.
    """

    practice_id: UUID
    name: str
    method_id: UUID
    site_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Practice aggregate emits.
# Add new event classes above and extend this alias when new slices
# land (6d-2: PracticeVersioned, PracticeDeprecated).
PracticeEvent = PracticeDefined


def event_type_name(event: PracticeEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: PracticeEvent) -> dict[str, Any]:
    """Serialize a Practice event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case PracticeDefined(
            practice_id=practice_id,
            name=name,
            method_id=method_id,
            site_id=site_id,
            occurred_at=occurred_at,
        ):
            return {
                "practice_id": str(practice_id),
                "name": name,
                "method_id": str(method_id),
                "site_id": str(site_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> PracticeEvent:
    """Rebuild a Practice event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "PracticeDefined":
            return PracticeDefined(
                practice_id=UUID(payload["practice_id"]),
                name=payload["name"],
                method_id=UUID(payload["method_id"]),
                site_id=UUID(payload["site_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown PracticeEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "PracticeDefined",
    "PracticeEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
