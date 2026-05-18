"""Vertical slice for the `DefineFamily` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.equipment.features import define_family

    cmd = define_family.DefineFamily(name="...", affordances=frozenset())
    handler = define_family.bind(deps)
    family_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.define_family import tool
from cora.equipment.features.define_family.command import DefineFamily
from cora.equipment.features.define_family.decider import decide
from cora.equipment.features.define_family.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.define_family.route import router

__all__ = [
    "DefineFamily",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
