"""Vertical slice for the `DecommissionAsset` command.

Module-as-namespace surface:

    from cora.equipment.features import decommission_asset

    cmd = decommission_asset.DecommissionAsset(asset_id=...)
    handler = decommission_asset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.decommission_asset import tool
from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.decider import decide
from cora.equipment.features.decommission_asset.handler import Handler, bind
from cora.equipment.features.decommission_asset.route import router

__all__ = [
    "DecommissionAsset",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
