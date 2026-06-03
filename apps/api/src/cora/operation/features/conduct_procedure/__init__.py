"""Vertical slice for the `ConductProcedure` command.

Operator-facing orchestration entry point: hands control to the
`Conductor` runtime which walks the supplied step list end-to-end
through the Procedure FSM (start -> execute -> complete | abort).
Returns a structured `ConductProcedureResult`; step-level failures are
encoded in the result, not raised, so a single client code-path
covers every outcome.

    from cora.operation.features import conduct_procedure

    cmd = conduct_procedure.ConductProcedure(procedure_id=..., steps=(...))
    handler = conduct_procedure.bind(deps, conductor=conductor)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.conduct_procedure import tool
from cora.operation.features.conduct_procedure.command import (
    ConductProcedure,
    ConductProcedureResult,
)
from cora.operation.features.conduct_procedure.handler import Handler, bind
from cora.operation.features.conduct_procedure.route import (
    ConductProcedureRequest,
    ConductProcedureResponse,
    router,
)

__all__ = [
    "ConductProcedure",
    "ConductProcedureRequest",
    "ConductProcedureResponse",
    "ConductProcedureResult",
    "Handler",
    "bind",
    "router",
    "tool",
]
