"""Slice: issue a new version label for an existing Capability.

Vertical slice (Phase 6k).
"""

from cora.recipe.features.version_capability import tool
from cora.recipe.features.version_capability.command import VersionCapability
from cora.recipe.features.version_capability.decider import decide
from cora.recipe.features.version_capability.handler import Handler, bind
from cora.recipe.features.version_capability.route import router

__all__ = [
    "Handler",
    "VersionCapability",
    "bind",
    "decide",
    "router",
    "tool",
]
