"""Vertical slice for the `RelocateAsset` command.

Module-as-namespace surface:

    from cora.equipment.features import relocate_asset

    cmd = relocate_asset.RelocateAsset(asset_id=..., to_parent_id=..., reason=...)
    handler = relocate_asset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.relocate_asset import tool
from cora.equipment.features.relocate_asset.command import RelocateAsset
from cora.equipment.features.relocate_asset.decider import decide
from cora.equipment.features.relocate_asset.handler import Handler, bind
from cora.equipment.features.relocate_asset.route import router

__all__ = [
    "Handler",
    "RelocateAsset",
    "bind",
    "decide",
    "router",
    "tool",
]
