"""Vertical slice for the `SuspendPermit` command.

Module-as-namespace surface, symmetric with the other Permit
transition slices:

    from cora.federation.features import suspend_permit

    cmd = suspend_permit.SuspendPermit(permit_id=..., reason=None)
    handler = suspend_permit.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.federation.features.suspend_permit import tool
from cora.federation.features.suspend_permit.command import SuspendPermit
from cora.federation.features.suspend_permit.decider import decide
from cora.federation.features.suspend_permit.handler import Handler, bind
from cora.federation.features.suspend_permit.route import router

__all__ = [
    "Handler",
    "SuspendPermit",
    "bind",
    "decide",
    "router",
    "tool",
]
