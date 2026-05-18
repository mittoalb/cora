"""Vertical slice for the `AddAssetFamily` command.

Module-as-namespace surface:

    from cora.equipment.features import add_asset_family

    cmd = add_asset_family.AddAssetFamily(asset_id=..., family_id=...)
    handler = add_asset_family.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.add_asset_family import tool
from cora.equipment.features.add_asset_family.command import AddAssetFamily
from cora.equipment.features.add_asset_family.decider import decide
from cora.equipment.features.add_asset_family.handler import Handler, bind
from cora.equipment.features.add_asset_family.route import router

__all__ = [
    "AddAssetFamily",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
