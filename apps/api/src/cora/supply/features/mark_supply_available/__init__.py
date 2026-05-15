"""Vertical slice for the `MarkSupplyAvailable` command.

Module-as-namespace surface, symmetric with the other transition
slices:

    from cora.supply.features import mark_supply_available

    cmd = mark_supply_available.MarkSupplyAvailable(
        supply_id=..., reason="operator walkdown confirms LN2 flowing"
    )
    handler = mark_supply_available.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.supply.features.mark_supply_available import tool
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.decider import decide
from cora.supply.features.mark_supply_available.handler import Handler, bind
from cora.supply.features.mark_supply_available.route import router

__all__ = [
    "Handler",
    "MarkSupplyAvailable",
    "bind",
    "decide",
    "router",
    "tool",
]
