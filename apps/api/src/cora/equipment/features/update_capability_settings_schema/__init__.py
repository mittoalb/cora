"""Vertical slice for the `UpdateCapabilitySettingsSchema` command."""

from cora.equipment.features.update_capability_settings_schema import tool
from cora.equipment.features.update_capability_settings_schema.command import (
    UpdateCapabilitySettingsSchema,
)
from cora.equipment.features.update_capability_settings_schema.decider import decide
from cora.equipment.features.update_capability_settings_schema.handler import Handler, bind
from cora.equipment.features.update_capability_settings_schema.route import router

__all__ = [
    "Handler",
    "UpdateCapabilitySettingsSchema",
    "bind",
    "decide",
    "router",
    "tool",
]
