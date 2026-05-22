"""Vertical slice for the `DefineCalibration` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.calibration.features import define_calibration

    cmd = define_calibration.DefineCalibration(
        subsystem_or_asset_id=..., quantity=..., operating_point={...},
    )
    handler = define_calibration.bind(deps)
    calibration_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.calibration.features.define_calibration import tool
from cora.calibration.features.define_calibration.command import DefineCalibration
from cora.calibration.features.define_calibration.decider import decide
from cora.calibration.features.define_calibration.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.calibration.features.define_calibration.route import router

__all__ = [
    "DefineCalibration",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
