"""Pure decider for the `StartProcedure` command.

Single-source genesis transition: `Defined -> Running`. Re-starting a
`Running` Procedure raises `ProcedureCannotStartError` (strict-not-
idempotent); starting any terminal raises the same.

Cross-aggregate validation: this is the third decider in the codebase
that takes upstream aggregate state as input (after Plan's
`define_plan` and Run's `start_run`). The handler pre-loads each
target Asset and (for Phase-of-Run Procedures) the Supply
satisfaction snapshot, passing them as a `ProcedureStartContext`.
The decider treats the loaded entities as opaque domain data.

## Validation order

1. State must not be None -> `ProcedureNotFoundError`.
2. State.status must be DEFINED -> `ProcedureCannotStartError`
   (single-source guard; mirrors complete_run's RUNNING-only guard).
3. No target Asset may be Decommissioned ->
   `ProcedurePlanAssetDecommissionedError` carrying the offending
   asset_ids (sorted for deterministic test assertions and operator
   readability).
4. For every kind in `needed_supplies_snapshot`, at least one Supply
   of that kind must be registered (`ProcedureRequiresAvailableSupplyError`
   when absent), AND at least one must be in status=Available
   (`ProcedureSupplyCoverageMismatchError` when present but none
   Available). Default-strict per [[project_supply_preflight_gate_design]].
   Standalone Procedures (no parent_run_id) pass the gate trivially
   because the handler hands an empty `needed_supplies_snapshot`.

## What's NOT validated

  - Decision approval (Decision BC integration deferred).
  - Subject hazard <= Method clearances (Method's hazardClearances
    facet not shipped; same deferral as RunStartContext).
  - Capability-level needed_supplies for standalone Procedures
    (Watch item per [[project_supply_preflight_gate_design]]).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotStartError,
    ProcedureNotFoundError,
    ProcedurePlanAssetDecommissionedError,
    ProcedureRequiresAvailableSupplyError,
    ProcedureStarted,
    ProcedureStatus,
    ProcedureSupplyCoverageMismatchError,
)
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.context import ProcedureStartContext

_STARTABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.DEFINED,)


def decide(
    state: Procedure | None,
    command: StartProcedure,
    *,
    context: ProcedureStartContext,
    needed_supplies_snapshot: frozenset[str] = frozenset(),
    now: datetime,
) -> list[ProcedureStarted]:
    """Decide the events produced by starting an existing Procedure.

    Invariants:
      - State must not be None -> ProcedureNotFoundError
      - Current status must be Defined -> ProcedureCannotStartError
      - No target Asset may be Decommissioned
        -> ProcedurePlanAssetDecommissionedError
      - Every kind in needed_supplies_snapshot must have at least
        one registered Supply -> ProcedureRequiresAvailableSupplyError
      - Every kind in needed_supplies_snapshot must have at least
        one AVAILABLE Supply -> ProcedureSupplyCoverageMismatchError
    """
    if state is None:
        raise ProcedureNotFoundError(command.procedure_id)
    if state.status not in _STARTABLE_STATUSES:
        raise ProcedureCannotStartError(state.id, current_status=state.status)

    decommissioned = sorted(
        (
            asset.id
            for asset in context.assets.values()
            if asset.lifecycle is AssetLifecycle.DECOMMISSIONED
        ),
        key=str,
    )
    if decommissioned:
        raise ProcedurePlanAssetDecommissionedError(decommissioned)

    # cross-BC Supply gate per [[project_supply_preflight_gate_design]]:
    # mirrors start_run's two-error pattern. Default-strict
    # (Degraded does NOT pass); operators with override authority use
    # mark_supply_available to declare a Supply Available before
    # starting. Standalone Procedures have empty needed_supplies_snapshot
    # and pass the gate trivially.
    for kind in sorted(needed_supplies_snapshot):
        candidates = context.needed_supplies_satisfaction.get(kind, ())
        if not candidates:
            raise ProcedureRequiresAvailableSupplyError(state.id, kind)
        if not any(s.status == "Available" for s in candidates):
            raise ProcedureSupplyCoverageMismatchError(
                state.id,
                kind,
                frozenset((s.supply_id, s.status) for s in candidates),
            )

    return [ProcedureStarted(procedure_id=state.id, occurred_at=now)]
