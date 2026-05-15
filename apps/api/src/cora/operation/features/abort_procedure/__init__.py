"""Vertical slice for the `AbortProcedure` command.

from cora.operation.features import abort_procedure

cmd = abort_procedure.AbortProcedure(procedure_id=..., reason="...")
handler = abort_procedure.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.abort_procedure import tool
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.abort_procedure.decider import decide
from cora.operation.features.abort_procedure.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.abort_procedure.route import router

__all__ = [
    "AbortProcedure",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
