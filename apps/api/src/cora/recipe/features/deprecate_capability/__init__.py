"""Slice: deprecate an existing Capability."""

from cora.recipe.features.deprecate_capability import tool
from cora.recipe.features.deprecate_capability.command import DeprecateCapability
from cora.recipe.features.deprecate_capability.decider import decide
from cora.recipe.features.deprecate_capability.handler import Handler, bind
from cora.recipe.features.deprecate_capability.route import router

__all__ = [
    "DeprecateCapability",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
