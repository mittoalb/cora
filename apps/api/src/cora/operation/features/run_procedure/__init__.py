"""Vertical slice for the `RunProcedure` command.

Operator-facing orchestration entry point: hands control to the
`Conductor` runtime which walks the supplied step list end-to-end
through the Procedure FSM (start -> execute -> complete | abort).
Returns a structured `RunProcedureResult`; step-level failures are
encoded in the result, not raised, so a single client code-path
covers every outcome.

    from cora.operation.features import run_procedure

    cmd = run_procedure.RunProcedure(procedure_id=..., steps=(...))
    handler = run_procedure.bind(deps, conductor=conductor)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.run_procedure import tool
from cora.operation.features.run_procedure.command import (
    RunProcedure,
    RunProcedureResult,
)
from cora.operation.features.run_procedure.handler import Handler, bind
from cora.operation.features.run_procedure.route import (
    RunProcedureRequest,
    RunProcedureResponse,
    router,
)

__all__ = [
    "Handler",
    "RunProcedure",
    "RunProcedureRequest",
    "RunProcedureResponse",
    "RunProcedureResult",
    "bind",
    "router",
    "tool",
]
