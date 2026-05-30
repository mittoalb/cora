"""Vertical slice for the `DecommissionFrame` command.

from cora.equipment.features import decommission_frame

cmd = decommission_frame.DecommissionFrame(frame_id=..., reason="...")
handler = decommission_frame.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.decommission_frame import tool
from cora.equipment.features.decommission_frame.command import DecommissionFrame
from cora.equipment.features.decommission_frame.context import DecommissionFrameContext
from cora.equipment.features.decommission_frame.decider import decide
from cora.equipment.features.decommission_frame.handler import Handler, bind
from cora.equipment.features.decommission_frame.route import router

__all__ = [
    "DecommissionFrame",
    "DecommissionFrameContext",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
