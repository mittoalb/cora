"""Slice: define a new Capability.

Vertical slice. Mirrors `define_family` (Equipment BC,
5j) and `define_method` (Recipe BC, 6a) in shape and discipline.
"""

from cora.recipe.features.define_capability import tool
from cora.recipe.features.define_capability.command import DefineCapability
from cora.recipe.features.define_capability.decider import decide
from cora.recipe.features.define_capability.handler import Handler, IdempotentHandler, bind
from cora.recipe.features.define_capability.route import router

__all__ = [
    "DefineCapability",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
