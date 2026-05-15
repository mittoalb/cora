"""Vertical slice for the `GetSupply` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.supply.features import get_supply

    q = get_supply.GetSupply(supply_id=...)
    handler = get_supply.bind(deps)
    supply = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.supply.features.get_supply import tool
from cora.supply.features.get_supply.handler import Handler, bind
from cora.supply.features.get_supply.query import GetSupply
from cora.supply.features.get_supply.route import router

__all__ = [
    "GetSupply",
    "Handler",
    "bind",
    "router",
    "tool",
]
