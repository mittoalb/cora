"""Vertical slice for the `UpdateFramePlacement` command.

from cora.equipment.features import update_frame_placement

cmd = update_frame_placement.UpdateFramePlacement(frame_id=..., new_placement=..., survey=None)
handler = update_frame_placement.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.update_frame_placement import tool
from cora.equipment.features.update_frame_placement.command import UpdateFramePlacement
from cora.equipment.features.update_frame_placement.decider import decide
from cora.equipment.features.update_frame_placement.handler import Handler, bind
from cora.equipment.features.update_frame_placement.route import router

__all__ = [
    "Handler",
    "UpdateFramePlacement",
    "bind",
    "decide",
    "router",
    "tool",
]
