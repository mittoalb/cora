"""Vertical slice for the `AppendProcedureSteps` command (Phase 10c-b iter 2).

Module-as-namespace surface:

    from cora.operation.features import append_procedure_step

    cmd = append_procedure_step.AppendProcedureSteps(
        procedure_id=..., entries=(...,)
    )
    handler = append_procedure_step.bind(deps, step_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits
`ProcedureStepsLogbookOpened` to the Procedure stream the first time
a step is appended for a Procedure; subsequent appends find the
logbook already attached and skip the open-event emission. Mirrors
6f-5b's `append_run_reading` precedent (which mirrors 8c-b's
`append_reasoning_entry`).
"""

from cora.operation.features.append_procedure_step import tool
from cora.operation.features.append_procedure_step.command import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_step.handler import Handler, bind
from cora.operation.features.append_procedure_step.route import router

__all__ = [
    "AppendProcedureSteps",
    "Handler",
    "ProcedureStepInput",
    "bind",
    "router",
    "tool",
]
