"""Vertical slice for the `UpdateFamilySettingsSchema` command."""

from cora.equipment.features.update_family_settings_schema import tool
from cora.equipment.features.update_family_settings_schema.command import (
    UpdateFamilySettingsSchema,
)
from cora.equipment.features.update_family_settings_schema.decider import decide
from cora.equipment.features.update_family_settings_schema.handler import Handler, bind
from cora.equipment.features.update_family_settings_schema.route import router

__all__ = [
    "Handler",
    "UpdateFamilySettingsSchema",
    "bind",
    "decide",
    "router",
    "tool",
]
