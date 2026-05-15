"""Domain events emitted by the Procedure aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 10c-a shipped `ProcedureRegistered`. Phase 10c-b adds the
three FSM-closure transition events:
  - `ProcedureStarted` -- single-source genesis transition (Defined ->
    Running). Slim payload: procedure_id + occurred_at. Mirrors
    `RunStarted`'s no-status convention; the start fact is what the
    event encodes.
  - `ProcedureCompleted` -- happy-path terminal (Running -> Completed).
    Slim payload by design; substantive completion summary (step count,
    duration, final check pass-rate) deferred until the step logbook
    has accreted real consumer signal.
  - `ProcedureAborted` -- emergency-exit terminal (Running -> Aborted).
    Payload carries `procedure_id` + free-form `reason: str` (1-500
    chars after trimming) + `occurred_at`. Mirrors RunAborted's reason
    shape exactly (free-form by design; structured taxonomy future-
    additive on the same triggers documented at
    `InvalidProcedureAbortReasonError`).

Phase 10c-b also adds `ProcedureStepsLogbookOpened` (lazy envelope
event for the per-step logbook table). Phase 10c-c adds
`ProcedureTruncated` (mirrors RunTruncated from 6f-4) and possibly
`ProcedureHeld / ProcedureResumed` if pilot needs surface.

## Payload conventions

`target_asset_ids` is stored as `list[UUID]` in payloads (events
carry primitives; lists JSON-serialize cleanly). The evolver
converts to `frozenset` when folding into Procedure state. The list
is sorted by string form in `to_payload` so the same logical Asset
set serializes deterministically -- important for hash-based
idempotency. Same precedent as Method's needs_capabilities (6a) and
Plan's asset_ids (6e-1).

`parent_run_id` is stored as `str | None` in payloads (UUID
serialized via `str()` when present). Optional binding: standalone
procedures (bakeouts, calibration sweeps between Runs) have None;
Phase-of-Run procedures have the parent Run's id.

Status is NOT carried in event payloads -- the event type itself
encodes the state change. Same precedent as `RunStarted` /
`SupplyRegistered` / `SubjectMounted`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.logbook import LogbookSchema
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ProcedureRegistered:
    """A new procedure was registered (lands in `Defined`).

    Status is implicit (`Defined`) -- the evolver sets it.

    `target_asset_ids` carries the Asset ids the procedure acts on;
    eventual-consistency stance, no cross-aggregate verification at
    register time. Existence + Decommissioned-lifecycle gating
    happens at start_procedure time in 10c-b via
    `ProcedureStartContext`.

    `parent_run_id` carries the optional Run binding (None for
    standalone procedures, set for Phase-of-Run procedures).
    """

    procedure_id: UUID
    name: str
    kind: str
    target_asset_ids: list[UUID]
    parent_run_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureStarted:
    """A Procedure transitioned out of Defined into Running (10c-b).

    Slim payload by design: the start fact is what the event encodes.
    Status is implicit (`Running`); the evolver sets it. No reason
    field (mirrors RunStarted; the operator already supplied name +
    kind + targets at register time).

    The `start_procedure` handler pre-loads each target Asset before
    reaching the decider; Decommissioned-state guarding lives in the
    decider via `ProcedureStartContext` (mirror of `RunStartContext`).
    """

    procedure_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureCompleted:
    """A Procedure reached its happy-path terminal (Running -> Completed).

    Slim payload by design (mirrors RunCompleted): substantive
    completion summary (step count, final check pass-rate, duration)
    deferred until the step logbook consumer signal surfaces. Today
    consumers needing post-completion read state should fold the
    Procedure stream (short and bounded for terminal-by-design
    Lifecycle Aggregates).
    """

    procedure_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureStepsLogbookOpened:
    """A steps logbook was attached to this Procedure (Phase 10c-b iter 2).

    Naming note: this event carries the entry-noun (`Steps`) in its name,
    vs. Conduit/Decision's bare `<Aggregate>LogbookOpened`. Same rationale
    as Run BC's `RunReadingLogbookOpened`: Procedure is planned to host
    multiple logbook kinds in the future (operator-action audit, hazard
    observations are likely future additions), so the event name carries
    the entry-noun discriminator upfront. Per
    [[project_logbook_entry_storage]] cross-BC family table.

    Lazy open-on-first-write: emitted by the `append_procedure_step`
    handler the first time a step is appended for this Procedure, NOT by
    `start_procedure` (mirrors Decision BC's 8c-b precedent for
    `DecisionLogbookOpened` and Run BC's 6f-5b precedent for
    `RunReadingLogbookOpened`). Subsequent appends find the logbook
    already attached and skip the open-event emission.

    `kind` discriminates the logbook category. Today only
    `LOGBOOK_KIND_STEPS` from state.py; future per-Procedure logbook
    kinds (operator-action audit, hazard) would use distinct constants
    and distinct state fields, not additional values for `kind` here.

    `schema` declares the row shape of `entries_operation_procedure_steps`,
    documenting the polymorphic `(step_kind, payload, sampled_at,
    occurred_at, recorded_at)` shape for downstream projections.

    No `ProcedureStepsLogbookClosed` event today: Procedure.status
    terminals (Completed | Aborted | Truncated) are the implicit close
    signal; `append_procedure_step` rejects writes when status is not
    Running via `ProcedureStepsLogbookClosedError`. Audit fidelity is
    preserved: the open event timestamps the logbook lifecycle start;
    the terminal ProcedureCompleted / ProcedureAborted / etc. event
    timestamps the lifecycle end.
    """

    procedure_id: UUID
    logbook_id: UUID
    kind: str
    schema: LogbookSchema
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureAborted:
    """A Procedure reached its emergency-exit terminal (Running -> Aborted).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirror of RunAborted.reason
    shape; same future-additive structured-taxonomy posture parked
    at `InvalidProcedureAbortReasonError`.

    Single-source guard at the decider (Running only). Held/Resumed
    deferred to 10c-c per pilot need; if Held lands, the abort source
    set widens to `Running | Held` to match Run BC's precedent.
    """

    procedure_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Procedure aggregate emits.
# 10c-b iter 1 closed the FSM with the three transition events;
# 10c-b iter 2 added the per-step logbook envelope event
# `ProcedureStepsLogbookOpened` (lazy-open on first append).
ProcedureEvent = (
    ProcedureRegistered
    | ProcedureStarted
    | ProcedureCompleted
    | ProcedureAborted
    | ProcedureStepsLogbookOpened
)


def event_type_name(event: ProcedureEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ProcedureEvent) -> dict[str, Any]:
    """Serialize a Procedure event to a JSON-friendly dict for jsonb storage.

    `target_asset_ids` is sorted by UUID string form so the persisted
    payload is deterministic -- same logical Asset set, same payload
    bytes, same idempotency hash. Same precedent as Method's
    PolicyDefined / MethodDefined.
    """
    match event:
        case ProcedureRegistered(
            procedure_id=procedure_id,
            name=name,
            kind=kind,
            target_asset_ids=target_asset_ids,
            parent_run_id=parent_run_id,
            occurred_at=occurred_at,
        ):
            return {
                "procedure_id": str(procedure_id),
                "name": name,
                "kind": kind,
                "target_asset_ids": sorted(str(a) for a in target_asset_ids),
                "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureStarted(procedure_id=procedure_id, occurred_at=occurred_at):
            return {
                "procedure_id": str(procedure_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureCompleted(procedure_id=procedure_id, occurred_at=occurred_at):
            return {
                "procedure_id": str(procedure_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureAborted(procedure_id=procedure_id, reason=reason, occurred_at=occurred_at):
            return {
                "procedure_id": str(procedure_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureStepsLogbookOpened(
            procedure_id=procedure_id,
            logbook_id=logbook_id,
            kind=kind,
            schema=schema,
            occurred_at=occurred_at,
        ):
            return {
                "procedure_id": str(procedure_id),
                "logbook_id": str(logbook_id),
                "kind": kind,
                "schema": schema.to_dict(),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ProcedureEvent:
    """Rebuild a Procedure event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    NOTE: 10c-a uses strict `payload[...]` indexing because every key
    in `ProcedureRegistered` is required at the schema level. When 10c-b
    adds optional facets to the genesis payload (for example
    `expected_step_count`, `triggered_by`, `requested_supply_kinds`),
    those new keys MUST use `payload.get("k", default)` so pre-10c-b
    streams fold cleanly without backfill. Same additive-evolution
    pattern as `recipe/aggregates/method/events.py:from_stored`
    (`needs_supplies` added in 10b).
    """
    payload = stored.payload
    match stored.event_type:
        case "ProcedureRegistered":
            raw_parent = payload["parent_run_id"]
            return ProcedureRegistered(
                procedure_id=UUID(payload["procedure_id"]),
                name=payload["name"],
                kind=payload["kind"],
                target_asset_ids=[UUID(a) for a in payload["target_asset_ids"]],
                parent_run_id=UUID(raw_parent) if raw_parent is not None else None,
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "ProcedureStarted":
            return ProcedureStarted(
                procedure_id=UUID(payload["procedure_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "ProcedureCompleted":
            return ProcedureCompleted(
                procedure_id=UUID(payload["procedure_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "ProcedureAborted":
            return ProcedureAborted(
                procedure_id=UUID(payload["procedure_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "ProcedureStepsLogbookOpened":
            return ProcedureStepsLogbookOpened(
                procedure_id=UUID(payload["procedure_id"]),
                logbook_id=UUID(payload["logbook_id"]),
                kind=payload["kind"],
                schema=LogbookSchema.from_dict(payload["schema"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown ProcedureEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ProcedureAborted",
    "ProcedureCompleted",
    "ProcedureEvent",
    "ProcedureRegistered",
    "ProcedureStarted",
    "ProcedureStepsLogbookOpened",
    "event_type_name",
    "from_stored",
    "to_payload",
]
