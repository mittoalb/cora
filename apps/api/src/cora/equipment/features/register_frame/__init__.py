"""Vertical slice for the `RegisterFrame` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.equipment.features import register_frame

    cmd = register_frame.RegisterFrame(
        name=..., parent_frame_id=..., placement=...,
    )
    handler = register_frame.bind(deps)
    frame_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.register_frame import tool
from cora.equipment.features.register_frame.command import RegisterFrame
from cora.equipment.features.register_frame.decider import decide
from cora.equipment.features.register_frame.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.register_frame.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterFrame",
    "bind",
    "decide",
    "router",
    "tool",
]
