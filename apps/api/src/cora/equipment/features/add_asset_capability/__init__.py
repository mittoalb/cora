"""Vertical slice for the `AddAssetCapability` command.

Module-as-namespace surface:

    from cora.equipment.features import add_asset_capability

    cmd = add_asset_capability.AddAssetCapability(asset_id=..., capability_id=...)
    handler = add_asset_capability.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.add_asset_capability import tool
from cora.equipment.features.add_asset_capability.command import AddAssetCapability
from cora.equipment.features.add_asset_capability.decider import decide
from cora.equipment.features.add_asset_capability.handler import Handler, bind
from cora.equipment.features.add_asset_capability.route import router

__all__ = [
    "AddAssetCapability",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
