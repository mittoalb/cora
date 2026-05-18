"""Vertical slice for the `VersionFamily` command.

Module-as-namespace surface:

    from cora.equipment.features import version_family

    cmd = version_family.VersionFamily(family_id=..., version_tag="v2")
    handler = version_family.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.version_family import tool
from cora.equipment.features.version_family.command import VersionFamily
from cora.equipment.features.version_family.decider import decide
from cora.equipment.features.version_family.handler import Handler, bind
from cora.equipment.features.version_family.route import router

__all__ = [
    "Handler",
    "VersionFamily",
    "bind",
    "decide",
    "router",
    "tool",
]
