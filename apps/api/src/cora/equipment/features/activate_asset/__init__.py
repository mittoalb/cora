"""Vertical slice for the `ActivateAsset` command.

Module-as-namespace surface:

    from cora.equipment.features import activate_asset

    cmd = activate_asset.ActivateAsset(asset_id=...)
    handler = activate_asset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.activate_asset import tool
from cora.equipment.features.activate_asset.command import ActivateAsset
from cora.equipment.features.activate_asset.decider import decide
from cora.equipment.features.activate_asset.handler import Handler, bind
from cora.equipment.features.activate_asset.route import router

__all__ = [
    "ActivateAsset",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
