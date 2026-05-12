"""The `list_assets` query slice. Cursor-paginated; backed by
`proj_equipment_asset_summary`."""

from cora.equipment.features.list_assets.handler import (
    AssetListPage,
    AssetSummaryItem,
    Handler,
    bind,
)
from cora.equipment.features.list_assets.query import ListAssets
from cora.equipment.features.list_assets.route import router

__all__ = [
    "AssetListPage",
    "AssetSummaryItem",
    "Handler",
    "ListAssets",
    "bind",
    "router",
]
