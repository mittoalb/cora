"""Vertical slice for the `GetClearance` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.safety.features import get_clearance

    q = get_clearance.GetClearance(clearance_id=...)
    handler = get_clearance.bind(deps)
    clearance = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.safety.features.get_clearance import tool
from cora.safety.features.get_clearance.handler import Handler, bind
from cora.safety.features.get_clearance.query import GetClearance
from cora.safety.features.get_clearance.route import router

__all__ = [
    "GetClearance",
    "Handler",
    "bind",
    "router",
    "tool",
]
