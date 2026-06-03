"""Vertical slice for the `AttachAssetToFixture` command."""

from cora.equipment.features.attach_asset_to_fixture import tool
from cora.equipment.features.attach_asset_to_fixture.command import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture.context import (
    AttachAssetToFixtureContext,
)
from cora.equipment.features.attach_asset_to_fixture.decider import decide
from cora.equipment.features.attach_asset_to_fixture.handler import Handler, bind
from cora.equipment.features.attach_asset_to_fixture.route import router

__all__ = [
    "AttachAssetToFixture",
    "AttachAssetToFixtureContext",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
