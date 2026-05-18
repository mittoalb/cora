"""Vertical slice for the `DeprecateFamily` command.

Module-as-namespace surface:

    from cora.equipment.features import deprecate_family

    cmd = deprecate_family.DeprecateFamily(family_id=...)
    handler = deprecate_family.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.deprecate_family import tool
from cora.equipment.features.deprecate_family.command import DeprecateFamily
from cora.equipment.features.deprecate_family.decider import decide
from cora.equipment.features.deprecate_family.handler import Handler, bind
from cora.equipment.features.deprecate_family.route import router

__all__ = [
    "DeprecateFamily",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
