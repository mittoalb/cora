"""Vertical slice for the `StartProcedure` command.

Module-as-namespace surface, symmetric with `start_run` (the closest
sibling: both are transition slices that pre-load cross-aggregate
state for the decider):

    from cora.operation.features import start_procedure

    cmd = start_procedure.StartProcedure(procedure_id=...)
    handler = start_procedure.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.start_procedure import tool
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.context import ProcedureStartContext
from cora.operation.features.start_procedure.decider import decide
from cora.operation.features.start_procedure.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.start_procedure.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "ProcedureStartContext",
    "StartProcedure",
    "bind",
    "decide",
    "router",
    "tool",
]
