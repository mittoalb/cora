"""Vertical slice for the `UpdateFrame` command.

from cora.equipment.features import update_frame

cmd = update_frame.UpdateFrame(frame_id=..., new_placement=..., survey=None)
handler = update_frame.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.update_frame import tool
from cora.equipment.features.update_frame.command import UpdateFrame
from cora.equipment.features.update_frame.decider import decide
from cora.equipment.features.update_frame.handler import Handler, bind
from cora.equipment.features.update_frame.route import router

__all__ = [
    "Handler",
    "UpdateFrame",
    "bind",
    "decide",
    "router",
    "tool",
]
