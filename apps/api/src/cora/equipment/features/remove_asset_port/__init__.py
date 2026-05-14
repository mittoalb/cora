"""Vertical slice for the `RemoveAssetPort` command (Phase 5h).

Mirror of `add_asset_port`. Removes a port by name; rejects when
the asset is Decommissioned or no port with that name exists.
"""

from cora.equipment.features.remove_asset_port import tool
from cora.equipment.features.remove_asset_port.command import RemoveAssetPort
from cora.equipment.features.remove_asset_port.decider import decide
from cora.equipment.features.remove_asset_port.handler import Handler, bind
from cora.equipment.features.remove_asset_port.route import router

__all__ = [
    "Handler",
    "RemoveAssetPort",
    "bind",
    "decide",
    "router",
    "tool",
]
