"""Vertical slice for the `RemoveAssetFamily` command.

Module-as-namespace surface:

    from cora.equipment.features import remove_asset_family

    cmd = remove_asset_family.RemoveAssetFamily(asset_id=..., family_id=...)
    handler = remove_asset_family.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.remove_asset_family import tool
from cora.equipment.features.remove_asset_family.command import RemoveAssetFamily
from cora.equipment.features.remove_asset_family.decider import decide
from cora.equipment.features.remove_asset_family.handler import Handler, bind
from cora.equipment.features.remove_asset_family.route import router

__all__ = [
    "Handler",
    "RemoveAssetFamily",
    "bind",
    "decide",
    "router",
    "tool",
]
