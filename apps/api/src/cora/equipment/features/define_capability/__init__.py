"""Vertical slice for the `DefineCapability` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.equipment.features import define_capability

    cmd = define_capability.DefineCapability(name="...")
    handler = define_capability.bind(deps)
    capability_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.define_capability import tool
from cora.equipment.features.define_capability.command import DefineCapability
from cora.equipment.features.define_capability.decider import decide
from cora.equipment.features.define_capability.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.define_capability.route import router

__all__ = [
    "DefineCapability",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
