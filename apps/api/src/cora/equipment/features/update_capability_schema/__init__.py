"""Vertical slice for the `UpdateCapabilitySchema` command."""

from cora.equipment.features.update_capability_schema import tool
from cora.equipment.features.update_capability_schema.command import UpdateCapabilitySchema
from cora.equipment.features.update_capability_schema.decider import decide
from cora.equipment.features.update_capability_schema.handler import Handler, bind
from cora.equipment.features.update_capability_schema.route import router

__all__ = [
    "Handler",
    "UpdateCapabilitySchema",
    "bind",
    "decide",
    "router",
    "tool",
]
