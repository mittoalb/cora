"""Vertical slice for the `GetAsset` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.equipment.features import get_asset

    q = get_asset.GetAsset(asset_id=...)
    handler = get_asset.bind(deps)
    asset = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.get_asset import tool
from cora.equipment.features.get_asset.handler import Handler, bind
from cora.equipment.features.get_asset.query import GetAsset
from cora.equipment.features.get_asset.route import router

__all__ = [
    "GetAsset",
    "Handler",
    "bind",
    "router",
    "tool",
]
