"""Vertical slice for the `UninstallAsset` command."""

from cora.equipment.features.uninstall_asset import tool
from cora.equipment.features.uninstall_asset.command import UninstallAsset
from cora.equipment.features.uninstall_asset.decider import decide
from cora.equipment.features.uninstall_asset.handler import Handler, bind
from cora.equipment.features.uninstall_asset.route import router

__all__ = ["Handler", "UninstallAsset", "bind", "decide", "router", "tool"]
