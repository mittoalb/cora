"""Vertical slice for the `DeregisterSupply` command."""

from cora.supply.features.deregister_supply import tool
from cora.supply.features.deregister_supply.command import DeregisterSupply
from cora.supply.features.deregister_supply.decider import decide
from cora.supply.features.deregister_supply.handler import Handler, bind
from cora.supply.features.deregister_supply.route import router

__all__ = [
    "DeregisterSupply",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
