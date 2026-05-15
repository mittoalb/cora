"""Pure decider for the `StartProcedure` command.

Single-source genesis transition: `Defined -> Running`. Re-starting a
`Running` Procedure raises `ProcedureCannotStartError` (strict-not-
idempotent); starting any terminal raises the same.

Cross-aggregate validation: this is the third decider in the codebase
that takes upstream aggregate state as input (after Plan's
`define_plan` and Run's `start_run`). The handler pre-loads each
target Asset and passes them as a `ProcedureStartContext`. The
decider treats the loaded entities as opaque domain data.

## Validation order

1. State must not be None -> `ProcedureNotFoundError`.
2. State.status must be DEFINED -> `ProcedureCannotStartError`
   (single-source guard; mirrors complete_run's RUNNING-only guard).
3. No target Asset may be Decommissioned ->
   `ProcedureAssetDecommissionedError` carrying the offending
   asset_ids (sorted for deterministic test assertions and operator
   readability).

## What's NOT validated

  - Supply availability (Supply BC integration deferred per
    [[project_operation_design]] watch item).
  - Decision approval (Decision BC integration deferred).
  - Subject hazard <= Method clearances (Method's hazardClearances
    facet not shipped; same deferral as RunStartContext).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureAssetDecommissionedError,
    ProcedureCannotStartError,
    ProcedureNotFoundError,
    ProcedureStarted,
    ProcedureStatus,
)
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.context import ProcedureStartContext

_STARTABLE_STATUSES: tuple[ProcedureStatus, ...] = (ProcedureStatus.DEFINED,)


def decide(
    state: Procedure | None,
    command: StartProcedure,
    *,
    context: ProcedureStartContext,
    now: datetime,
) -> list[ProcedureStarted]:
    """Decide the events produced by starting an existing Procedure."""
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
        raise ProcedureAssetDecommissionedError(decommissioned)

    return [ProcedureStarted(procedure_id=state.id, occurred_at=now)]
