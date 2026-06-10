"""Vertical slice for the `BindAssetToFacility` command.

Post-genesis cross-BC binding of an existing Asset to its owning
Federation Facility. Set-once per [[project-slice8-design]] L2.
Mirrors the Slice 8A register_asset facility_code path: same
FacilityLookup port, same AssetFacilityNotFoundError on unknown
slugs, same Decommissioned-Facility-binding-allowed rule.
"""

from cora.equipment.features.bind_asset_to_facility import tool
from cora.equipment.features.bind_asset_to_facility.command import BindAssetToFacility
from cora.equipment.features.bind_asset_to_facility.decider import decide
from cora.equipment.features.bind_asset_to_facility.handler import Handler, bind
from cora.equipment.features.bind_asset_to_facility.route import router

__all__ = [
    "BindAssetToFacility",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
