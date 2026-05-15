"""Evolver: replay events to reconstruct Procedure state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `ProcedureEvent` without a matching match arm here.

Status mapping per event type (10c-a ships only the genesis arm;
transition arms land in 10c-b/c):
  - `ProcedureRegistered` -> DEFINED (genesis; universal initial-state convention)

The mapping is hardcoded per match arm -- the event type IS the
state-change indicator. Same precedent as `CapabilityDefined ->
DEFINED` / `SubjectMounted -> MOUNTED` / `SupplyRegistered ->
UNKNOWN`.

`target_asset_ids` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state). Order doesn't matter at the state
layer (set semantics for ProcedureStartContext lookup); the payload
already sorted in `to_payload` for persistence determinism.

The shared `require_state` helper at `cora.infrastructure.evolver`
keeps per-arm bodies short (hoisted post-7e once the 11th identical
copy landed; Procedure is the next evolver to use it on day one
when transition arms land in 10c-b).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.operation.aggregates.procedure.events import (
    ProcedureEvent,
    ProcedureRegistered,
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
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ProcedureEvent]) -> Procedure | None:
    """Replay a stream of events from the empty initial state."""
    state: Procedure | None = None
    for event in events:
        state = evolve(state, event)
    return state
