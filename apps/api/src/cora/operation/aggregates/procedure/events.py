"""Domain events emitted by the Procedure aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 10c-a ships `ProcedureRegistered` only. Phase 10c-b adds the
transition events (`ProcedureStarted`, `ProcedureCompleted`,
`ProcedureAborted`) plus the lazy `ProcedureStepsLogbookOpened`
envelope event for the per-step substream. Phase 10c-c adds
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


# Discriminated union of every event the Procedure aggregate emits.
# 10c-a ships only ProcedureRegistered; transition events join in 10c-b.
ProcedureEvent = ProcedureRegistered


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
        case _:
            msg = f"Unknown ProcedureEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ProcedureEvent",
    "ProcedureRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
