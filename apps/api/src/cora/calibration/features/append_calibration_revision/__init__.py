"""Vertical slice for the `AppendCalibrationRevision` command.

Append-only revision growth on an existing Calibration. Idempotency-
Key wrapped per the design memo (agent-subscriber caller pattern
needs exactly-once-effective semantics across retries).
"""

from cora.calibration.features.append_calibration_revision import tool
from cora.calibration.features.append_calibration_revision.command import (
    AppendCalibrationRevision,
)
from cora.calibration.features.append_calibration_revision.decider import decide
from cora.calibration.features.append_calibration_revision.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.calibration.features.append_calibration_revision.route import router

__all__ = [
    "AppendCalibrationRevision",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
