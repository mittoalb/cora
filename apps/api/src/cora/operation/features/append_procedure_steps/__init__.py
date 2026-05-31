"""Vertical slice for the `AppendProcedureSteps` command.

Module-as-namespace surface:

    from cora.operation.features import append_procedure_steps

    cmd = append_procedure_steps.AppendProcedureSteps(
        procedure_id=..., entries=(...,)
    )
    handler = append_procedure_steps.bind(deps, step_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits
`ProcedureStepsLogbookOpened` to the Procedure stream the first time
a step is appended for a Procedure; subsequent appends find the
logbook already attached and skip the open-event emission. Mirrors
Run BC's `append_run_readings` precedent (which mirrors Decision BC's
`append_reasoning_entries`).
"""

from cora.operation.features.append_procedure_steps import tool
from cora.operation.features.append_procedure_steps.command import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_steps.handler import Handler, bind
from cora.operation.features.append_procedure_steps.route import router

__all__ = [
    "AppendProcedureSteps",
    "Handler",
    "ProcedureStepInput",
    "bind",
    "router",
    "tool",
]
