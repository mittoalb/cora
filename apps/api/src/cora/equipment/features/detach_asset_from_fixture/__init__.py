"""Vertical slice for the `DetachAssetFromFixture` command."""

from cora.equipment.features.detach_asset_from_fixture import tool
from cora.equipment.features.detach_asset_from_fixture.command import DetachAssetFromFixture
from cora.equipment.features.detach_asset_from_fixture.decider import decide
from cora.equipment.features.detach_asset_from_fixture.handler import Handler, bind
from cora.equipment.features.detach_asset_from_fixture.route import router

__all__ = [
    "DetachAssetFromFixture",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
