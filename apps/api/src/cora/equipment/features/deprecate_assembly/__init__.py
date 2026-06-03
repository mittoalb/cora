"""Vertical slice for the `DeprecateAssembly` command."""

from cora.equipment.features.deprecate_assembly import tool
from cora.equipment.features.deprecate_assembly.command import DeprecateAssembly
from cora.equipment.features.deprecate_assembly.decider import decide
from cora.equipment.features.deprecate_assembly.handler import Handler, bind
from cora.equipment.features.deprecate_assembly.route import router

__all__ = [
    "DeprecateAssembly",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
