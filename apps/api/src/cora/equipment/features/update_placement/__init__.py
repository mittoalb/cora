"""Vertical slice for the `UpdatePlacement` command."""

from cora.equipment.features.update_placement import tool
from cora.equipment.features.update_placement.command import UpdatePlacement
from cora.equipment.features.update_placement.decider import decide
from cora.equipment.features.update_placement.handler import Handler, bind
from cora.equipment.features.update_placement.route import router

__all__ = ["Handler", "UpdatePlacement", "bind", "decide", "router", "tool"]
