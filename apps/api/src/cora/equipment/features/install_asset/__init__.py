"""Vertical slice for the `InstallAsset` command."""

from cora.equipment.features.install_asset import tool
from cora.equipment.features.install_asset.command import InstallAsset
from cora.equipment.features.install_asset.context import InstallAssetContext
from cora.equipment.features.install_asset.decider import decide
from cora.equipment.features.install_asset.handler import Handler, bind
from cora.equipment.features.install_asset.route import router

__all__ = [
    "Handler",
    "InstallAsset",
    "InstallAssetContext",
    "bind",
    "decide",
    "router",
    "tool",
]
