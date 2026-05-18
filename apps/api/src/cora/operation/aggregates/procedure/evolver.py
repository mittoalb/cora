"""Evolver: replay events to reconstruct Procedure state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `ProcedureEvent` without a matching match arm here.

Status mapping per event type:
  - `ProcedureRegistered`         -> DEFINED   (genesis; universal initial-state convention)
  - `ProcedureStarted`            -> RUNNING   (single-source genesis transition out of Defined)
  - `ProcedureCompleted`          -> COMPLETED (happy-path terminal)
  - `ProcedureAborted`            -> ABORTED   (emergency-exit terminal)
  - `ProcedureTruncated`          -> TRUNCATED (partial-data terminal; mirrors RunTruncated)
  - `ProcedureStepsLogbookOpened` -> STATUS UNCHANGED (sets steps_logbook_id;
                                     lazy-open envelope event from
                                     append_procedure_step, orthogonal to lifecycle)

The mapping is hardcoded per match arm -- the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `RunStarted -> RUNNING` / `RunCompleted -> COMPLETED` /
`SubjectMounted -> MOUNTED`.

`target_asset_ids` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state). Order doesn't matter at the state
layer (set semantics for ProcedureStartContext lookup); the payload
already sorted in `to_payload` for persistence determinism.

**Critical invariant**: every transition arm MUST carry `id`, `name`,
`kind`, `target_asset_ids`, `parent_run_id`, `steps_logbook_id`,
AND `capability_id` (Phase 10d-additive) through from prior state.
Constructing `Procedure(id=..., name=..., status=...)` without
explicitly passing the additive fields would silently WIPE them to
defaults (empty frozenset / None). Pinned by the per-transition
preserve-fields tests. Same lesson as Run BC's evolver docstring.

`steps_logbook_id` (Phase 10c-b iter 2) is set by the
`ProcedureStepsLogbookOpened` arm (lazy open-on-first-write
triggered by `append_procedure_step`); all other arms preserve
whatever prior state held. Pre-10c-b-iter-2 streams fold with
`steps_logbook_id=None`.

The shared `require_state` helper at `cora.infrastructure.evolver`
keeps per-arm bodies short. Hoisted post-7e once the 11th identical
copy landed; Procedure adopts it on day one for the new transition
arms (10c-b).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.operation.aggregates.procedure.events import (
    ProcedureAborted,
    ProcedureCompleted,
    ProcedureEvent,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStepsLogbookOpened,
    ProcedureTruncated,
)
from cora.operation.aggregates.procedure.state import (
    Procedure,
    ProcedureName,
    ProcedureStatus,
)


def evolve(state: Procedure | None, event: ProcedureEvent) -> Procedure:
    """Apply one event to the current state."""
    match event:
        case ProcedureRegistered(
            procedure_id=procedure_id,
            name=name,
            kind=kind,
            target_asset_ids=target_asset_ids,
            parent_run_id=parent_run_id,
            capability_id=capability_id,
        ):
            _ = state  # ProcedureRegistered is the genesis event; prior state ignored
            return Procedure(
                id=procedure_id,
                name=ProcedureName(name),
                kind=kind,
                target_asset_ids=frozenset(target_asset_ids),
                status=ProcedureStatus.DEFINED,
                parent_run_id=parent_run_id,
                steps_logbook_id=None,
                capability_id=capability_id,
            )
        case ProcedureStarted():
            prior = require_state(state, "ProcedureStarted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.RUNNING,
                parent_run_id=prior.parent_run_id,
                steps_logbook_id=prior.steps_logbook_id,
                capability_id=prior.capability_id,
            )
        case ProcedureCompleted():
            prior = require_state(state, "ProcedureCompleted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.COMPLETED,
                parent_run_id=prior.parent_run_id,
                steps_logbook_id=prior.steps_logbook_id,
                capability_id=prior.capability_id,
            )
        case ProcedureAborted():
            prior = require_state(state, "ProcedureAborted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.ABORTED,
                parent_run_id=prior.parent_run_id,
                steps_logbook_id=prior.steps_logbook_id,
                capability_id=prior.capability_id,
            )
        case ProcedureTruncated():
            prior = require_state(state, "ProcedureTruncated")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.TRUNCATED,
                parent_run_id=prior.parent_run_id,
                steps_logbook_id=prior.steps_logbook_id,
                capability_id=prior.capability_id,
            )
        case ProcedureStepsLogbookOpened(logbook_id=logbook_id):
            # Lazy open-on-first-write (Phase 10c-b iter 2): preserve all
            # prior state, set steps_logbook_id. Status NOT touched -- the
            # logbook is orthogonal to lifecycle. Mirrors Run BC's
            # RunReadingLogbookOpened arm exactly.
            prior = require_state(state, "ProcedureStepsLogbookOpened")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=prior.status,
                parent_run_id=prior.parent_run_id,
                steps_logbook_id=logbook_id,
                capability_id=prior.capability_id,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ProcedureEvent]) -> Procedure | None:
    """Replay a stream of events from the empty initial state."""
    state: Procedure | None = None
    for event in events:
        state = evolve(state, event)
    return state
