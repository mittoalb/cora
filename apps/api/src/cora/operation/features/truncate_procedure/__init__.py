"""Vertical slice for the `TruncateProcedure` command.

from cora.operation.features import truncate_procedure

cmd = truncate_procedure.TruncateProcedure(
    procedure_id=..., reason="...", interrupted_at=...
)
handler = truncate_procedure.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.truncate_procedure import tool
from cora.operation.features.truncate_procedure.command import TruncateProcedure
from cora.operation.features.truncate_procedure.decider import decide
from cora.operation.features.truncate_procedure.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.truncate_procedure.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "TruncateProcedure",
    "bind",
    "decide",
    "router",
    "tool",
]
