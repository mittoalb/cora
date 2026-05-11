"""Domain events emitted by the Run aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 6f-1 ships `RunStarted` only. Subsequent phases:
  - 6f-2: RunCompleted, RunAborted (terminal happy + emergency exit)
  - 6f-3: RunHeld, RunResumed, RunStopped (defensive transitions)
  - 6f-4: RunTruncated (partial-data terminal; reason design TBD)
  - 6f-5: substream events (per-frame triggers, motor positions —
    NOT on the main Run stream; substream territory)

## Payload conventions

`plan_id` and `subject_id` carry as primitive UUIDs (or null for
subject_id in calibration runs). Eventual-consistency stance:
neither is verified at the persistence layer — handler pre-loads
both before reaching the decider.

Status is NOT carried in event payloads — the event type itself
encodes the state change. Same precedent as PracticeDefined /
MethodDefined / CapabilityDefined / SubjectMounted /
ActorDeactivated / PlanDefined.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class RunStarted:
    """A new Run was started: Plan + (optional) Subject binding established.

    Status is implicit (`Started`) — the evolver sets it.

    `plan_id` and `subject_id` are eventual-consistency refs (loaded
    at handler-load time; not re-verified at fold time). `subject_id`
    is null for dark-field / flat-field calibration runs per
    beamline-domain convention.
    """

    run_id: UUID
    name: str
    plan_id: UUID
    subject_id: UUID | None
    occurred_at: datetime


# Discriminated union of every event the Run aggregate emits.
# Single-element today; transitions land in 6f-2+.
RunEvent = RunStarted


def event_type_name(event: RunEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: RunEvent) -> dict[str, Any]:
    """Serialize a Run event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings. `subject_id` serializes as null when None (dark-field /
    calibration runs).
    """
    match event:
        case RunStarted(
            run_id=run_id,
            name=name,
            plan_id=plan_id,
            subject_id=subject_id,
            occurred_at=occurred_at,
        ):
            return {
                "run_id": str(run_id),
                "name": name,
                "plan_id": str(plan_id),
                "subject_id": str(subject_id) if subject_id is not None else None,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> RunEvent:
    """Rebuild a Run event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "RunStarted":
            raw_subject = payload["subject_id"]
            return RunStarted(
                run_id=UUID(payload["run_id"]),
                name=payload["name"],
                plan_id=UUID(payload["plan_id"]),
                subject_id=UUID(raw_subject) if raw_subject is not None else None,
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown RunEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "RunEvent",
    "RunStarted",
    "event_type_name",
    "from_stored",
    "to_payload",
]
