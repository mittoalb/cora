"""Vertical slice for the `CompleteProcedure` command.

from cora.operation.features import complete_procedure

cmd = complete_procedure.CompleteProcedure(procedure_id=...)
handler = complete_procedure.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.complete_procedure import tool
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.complete_procedure.decider import decide
from cora.operation.features.complete_procedure.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.complete_procedure.route import router

__all__ = [
    "CompleteProcedure",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
