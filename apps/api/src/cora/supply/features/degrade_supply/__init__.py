"""Vertical slice for the `DegradeSupply` command (10a-b).

Module-as-namespace surface, symmetric with mark_supply_available:

    from cora.supply.features import degrade_supply

    cmd = degrade_supply.DegradeSupply(supply_id=..., reason="...")
    handler = degrade_supply.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.supply.features.degrade_supply import tool
from cora.supply.features.degrade_supply.command import DegradeSupply
from cora.supply.features.degrade_supply.decider import decide
from cora.supply.features.degrade_supply.handler import Handler, bind
from cora.supply.features.degrade_supply.route import router

__all__ = [
    "DegradeSupply",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
