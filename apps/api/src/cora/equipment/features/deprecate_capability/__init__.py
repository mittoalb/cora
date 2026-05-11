"""Vertical slice for the `DeprecateCapability` command.

Module-as-namespace surface:

    from cora.equipment.features import deprecate_capability

    cmd = deprecate_capability.DeprecateCapability(capability_id=...)
    handler = deprecate_capability.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.deprecate_capability import tool
from cora.equipment.features.deprecate_capability.command import DeprecateCapability
from cora.equipment.features.deprecate_capability.decider import decide
from cora.equipment.features.deprecate_capability.handler import Handler, bind
from cora.equipment.features.deprecate_capability.route import router

__all__ = [
    "DeprecateCapability",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
