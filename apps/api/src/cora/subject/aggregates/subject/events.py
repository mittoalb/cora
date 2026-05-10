"""Domain events emitted by the Subject aggregate, plus the discriminated union.

Mirrors `cora/access/aggregates/actor/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Phase 4a shipped `SubjectRegistered`. Phase 4b adds `SubjectMounted`.
Remaining transition events (`MeasurementRecorded`, `SubjectRemoved`,
`SubjectReturned` / `SubjectStored` / `SubjectDiscarded`) land per
slice in 4c-4d.

Status is NOT carried in event payloads — the event type itself
encodes the state change (e.g., `SubjectMounted -> status=MOUNTED`).
The evolver hardcodes the mapping per match arm. Same precedent as
`ActorDeactivated -> is_active=False`. See state.py docstring for
the rationale.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class SubjectRegistered:
    """A new subject was registered with the facility.

    Status is implicit (`Received`) — the evolver sets it.
    """

    subject_id: UUID
    name: str
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectMounted:
    """A subject was mounted on the apparatus.

    Status transition: `Received -> Mounted`. The evolver sets the
    new status; no status field in the payload.
    """

    subject_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Subject aggregate emits. Add
# new event classes above and extend this alias when new slices land.
SubjectEvent = SubjectRegistered | SubjectMounted


def event_type_name(event: SubjectEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SubjectEvent) -> dict[str, Any]:
    """Serialize a Subject event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case SubjectRegistered(subject_id=subject_id, name=name, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectMounted(subject_id=subject_id, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> SubjectEvent:
    """Rebuild a Subject event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "SubjectRegistered":
            return SubjectRegistered(
                subject_id=UUID(payload["subject_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "SubjectMounted":
            return SubjectMounted(
                subject_id=UUID(payload["subject_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown SubjectEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "SubjectEvent",
    "SubjectMounted",
    "SubjectRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
