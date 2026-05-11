"""Vertical slice for the `GetCapability` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.equipment.features import get_capability

    q = get_capability.GetCapability(capability_id=...)
    handler = get_capability.bind(deps)
    capability = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.get_capability import tool
from cora.equipment.features.get_capability.handler import Handler, bind
from cora.equipment.features.get_capability.query import GetCapability
from cora.equipment.features.get_capability.route import router

__all__ = [
    "GetCapability",
    "Handler",
    "bind",
    "router",
    "tool",
]
