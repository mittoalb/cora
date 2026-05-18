"""Vertical slice for the `AppendRevision` command (Phase 12a-2).

Append-only revision growth on an existing Calibration. Idempotency-
Key wrapped per the design memo (agent-subscriber caller pattern
needs exactly-once-effective semantics across retries).
"""

from cora.calibration.features.append_revision import tool
from cora.calibration.features.append_revision.command import AppendRevision
from cora.calibration.features.append_revision.decider import decide
from cora.calibration.features.append_revision.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.calibration.features.append_revision.route import router

__all__ = [
    "AppendRevision",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
