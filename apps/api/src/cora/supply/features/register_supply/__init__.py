"""Vertical slice for the `RegisterSupply` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.supply.features import register_supply

    cmd = register_supply.RegisterSupply(
        kind="...", name="...", facility_code="..."
    )
    handler = register_supply.bind(deps)
    supply_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.supply.features.register_supply import tool
from cora.supply.features.register_supply.command import RegisterSupply
from cora.supply.features.register_supply.decider import decide
from cora.supply.features.register_supply.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.supply.features.register_supply.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterSupply",
    "bind",
    "decide",
    "router",
    "tool",
]
