"""Vertical slice for the `ActivatePermit` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import activate_permit

    cmd = activate_permit.ActivatePermit(permit_id=...)
    handler = activate_permit.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.federation.features.activate_permit import tool
from cora.federation.features.activate_permit.command import ActivatePermit
from cora.federation.features.activate_permit.decider import decide
from cora.federation.features.activate_permit.handler import Handler, bind
from cora.federation.features.activate_permit.route import router

__all__ = [
    "ActivatePermit",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
