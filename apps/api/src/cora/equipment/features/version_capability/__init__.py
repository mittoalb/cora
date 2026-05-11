"""Vertical slice for the `VersionCapability` command.

Module-as-namespace surface:

    from cora.equipment.features import version_capability

    cmd = version_capability.VersionCapability(capability_id=..., version_tag="v2")
    handler = version_capability.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.version_capability import tool
from cora.equipment.features.version_capability.command import VersionCapability
from cora.equipment.features.version_capability.decider import decide
from cora.equipment.features.version_capability.handler import Handler, bind
from cora.equipment.features.version_capability.route import router

__all__ = [
    "Handler",
    "VersionCapability",
    "bind",
    "decide",
    "router",
    "tool",
]
