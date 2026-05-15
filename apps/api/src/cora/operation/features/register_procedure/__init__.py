"""Vertical slice for the `RegisterProcedure` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.operation.features import register_procedure

    cmd = register_procedure.RegisterProcedure(
        name="...", kind="bakeout", target_asset_ids=frozenset({...}),
    )
    handler = register_procedure.bind(deps)
    procedure_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.register_procedure import tool
from cora.operation.features.register_procedure.command import RegisterProcedure
from cora.operation.features.register_procedure.decider import decide
from cora.operation.features.register_procedure.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.register_procedure.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterProcedure",
    "bind",
    "decide",
    "router",
    "tool",
]
