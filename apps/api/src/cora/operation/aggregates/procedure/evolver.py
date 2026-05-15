"""Evolver: replay events to reconstruct Procedure state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `ProcedureEvent` without a matching match arm here.

Status mapping per event type:
  - `ProcedureRegistered` -> DEFINED   (genesis; universal initial-state convention)
  - `ProcedureStarted`    -> RUNNING   (single-source genesis transition out of Defined)
  - `ProcedureCompleted`  -> COMPLETED (happy-path terminal)
  - `ProcedureAborted`    -> ABORTED   (emergency-exit terminal)

The mapping is hardcoded per match arm -- the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `RunStarted -> RUNNING` / `RunCompleted -> COMPLETED` /
`SubjectMounted -> MOUNTED`.

`target_asset_ids` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state). Order doesn't matter at the state
layer (set semantics for ProcedureStartContext lookup); the payload
already sorted in `to_payload` for persistence determinism.

**Critical invariant**: every transition arm MUST carry `id`, `name`,
`kind`, `target_asset_ids`, AND `parent_run_id` through from prior
state. Constructing `Procedure(id=..., name=..., status=...)` without
explicitly passing the additive fields would silently WIPE them to
defaults (empty frozenset / None). Pinned by the per-transition
preserve-fields tests. Same lesson as Run BC's evolver docstring.

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
        ):
            _ = state  # ProcedureRegistered is the genesis event; prior state ignored
            return Procedure(
                id=procedure_id,
                name=ProcedureName(name),
                kind=kind,
                target_asset_ids=frozenset(target_asset_ids),
                status=ProcedureStatus.DEFINED,
                parent_run_id=parent_run_id,
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
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ProcedureEvent]) -> Procedure | None:
    """Replay a stream of events from the empty initial state."""
    state: Procedure | None = None
    for event in events:
        state = evolve(state, event)
    return state
