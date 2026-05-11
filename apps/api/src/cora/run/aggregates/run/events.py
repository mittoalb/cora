"""Domain events emitted by the Run aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 6f-1 shipped `RunStarted`. Phase 6f-2 added:
  - `RunCompleted` — happy-path terminal (Running → Completed).
    Payload is `run_id` + `occurred_at` only; substantive run
    summary (frame_count, duration_ms, final detector positions,
    etc.) is deferred to 6f-5+ when DAQ-substream integration
    arrives. Per the fold-cost principles, the completion event
    SHOULD eventually carry summary state so consumers don't have
    to re-fold per-step history just to ask "what happened in
    Run X?" — but the substantive shape only crystallizes once
    the substream layer exists to source it.
  - `RunAborted` — emergency-exit terminal (Running | Held → Aborted).
    Payload carries `run_id` + free-form `reason: str` (1-500 chars)
    + `occurred_at`. Reason is stored as primitive string today;
    future-additive structured taxonomy is documented at
    `InvalidRunAbortReasonError` along with its three re-evaluation
    triggers. (Source set widened in 6f-3 to include `Held`.)

Phase 6f-3 adds the bidirectional pause cycle plus the controlled
exit terminal:
  - `RunHeld` — pause transition (Running → Held). Payload is
    `run_id` + `occurred_at` only. No reason field — matches PackML
    / Bluesky precedent (Hold / pause carries no domain reason in
    either standard). Holds are routine (alignment, brief beam
    dropout, operator break); reason field would be friction without
    audit value at this layer. Future-additive on the same triggers
    as RunAborted's reason if vocabulary / Decision BC integration /
    compliance demand crystallize.
  - `RunResumed` — resume transition (Held → Running). Payload is
    `run_id` + `occurred_at` only. Resume is just permission to
    proceed; no reason field.
  - `RunStopped` — controlled-exit terminal (Running | Held → Stopped).
    Payload carries `run_id` + free-form `reason: str` (1-500 chars)
    + `occurred_at`. Mirrors RunAborted shape — controlled-but-early
    terminal exit deserves audit explanation. Distinct from Aborted:
    Stopped data is valid up to the stop point; Aborted data is
    flagged as potentially invalid (PackML + Bluesky semantic
    distinction at the lifecycle layer; substream cleanup semantics
    materialize in 6f-5+).

Hold ⇄ Resume is a bidirectional cycle with unlimited repeats; the
event stream may interleave [RunStarted, RunHeld, RunResumed, RunHeld,
RunResumed, RunCompleted] with arbitrary cycle counts. The fold
preserves only the latest status; per-cycle audit lives in the
event stream itself.

Subsequent phases:
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

    Status is implicit (`Running`) — the evolver sets it.

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


@dataclass(frozen=True)
class RunHeld:
    """A Run was held (Running → Held).

    Slim payload — no reason field. Matches PackML / Bluesky
    precedent: Hold / pause is a routine operation (alignment,
    brief dropout, operator break) that doesn't reify a domain
    reason. Future-additive if the same re-evaluation triggers
    documented for RunAborted's reason field crystallize.
    """

    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunResumed:
    """A held Run was resumed (Held → Running).

    Slim payload by design — resume is just permission to proceed.
    """

    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunCompleted:
    """A Run reached its happy-path terminal (Running → Completed).

    Slim payload by design (gate-review Q3): substantive run
    summary lands in 6f-5+ once DAQ-substream integration is in
    place to source it. Today, downstream consumers needing
    aggregate read state should fold the Run stream — the stream
    is short for terminal-by-design Lifecycle Aggregates (a
    handful of lifecycle events, not per-frame data).
    """

    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RunAborted:
    """A Run reached its emergency-exit terminal (Running | Held → Aborted).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Future-additive structured
    taxonomy is parked at `InvalidRunAbortReasonError`'s docstring
    along with three concrete triggers for re-evaluation.

    Source set widened in 6f-3 to include `Held` — emergencies
    during a hold are real and should not require an intervening
    Resume.
    """

    run_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class RunStopped:
    """A Run reached its controlled-exit terminal (Running | Held → Stopped).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Same shape as RunAborted's
    reason; same future-additive structured-taxonomy posture.

    Distinct from Aborted at the lifecycle layer (data validity
    semantics): Stopped data is valid up to the stop point;
    Aborted data is flagged as potentially invalid. PackML +
    Bluesky precedent (Stop = controlled deceleration / clean
    exit; Abort = emergency, prioritises speed over orderly
    shutdown).
    """

    run_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Run aggregate emits.
RunEvent = RunStarted | RunHeld | RunResumed | RunCompleted | RunAborted | RunStopped


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
        case RunHeld(run_id=run_id, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunResumed(run_id=run_id, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunCompleted(run_id=run_id, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RunAborted(run_id=run_id, reason=reason, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case RunStopped(run_id=run_id, reason=reason, occurred_at=occurred_at):
            return {
                "run_id": str(run_id),
                "reason": reason,
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
        case "RunHeld":
            return RunHeld(
                run_id=UUID(payload["run_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "RunResumed":
            return RunResumed(
                run_id=UUID(payload["run_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "RunCompleted":
            return RunCompleted(
                run_id=UUID(payload["run_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "RunAborted":
            return RunAborted(
                run_id=UUID(payload["run_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "RunStopped":
            return RunStopped(
                run_id=UUID(payload["run_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown RunEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "RunAborted",
    "RunCompleted",
    "RunEvent",
    "RunHeld",
    "RunResumed",
    "RunStarted",
    "RunStopped",
    "event_type_name",
    "from_stored",
    "to_payload",
]
