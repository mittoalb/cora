"""Vertical slice for the `RemoveAssetCapability` command.

Module-as-namespace surface:

    from cora.equipment.features import remove_asset_capability

    cmd = remove_asset_capability.RemoveAssetCapability(asset_id=..., capability_id=...)
    handler = remove_asset_capability.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.remove_asset_capability import tool
from cora.equipment.features.remove_asset_capability.command import RemoveAssetCapability
from cora.equipment.features.remove_asset_capability.decider import decide
from cora.equipment.features.remove_asset_capability.handler import Handler, bind
from cora.equipment.features.remove_asset_capability.route import router

__all__ = [
    "Handler",
    "RemoveAssetCapability",
    "bind",
    "decide",
    "router",
    "tool",
]
