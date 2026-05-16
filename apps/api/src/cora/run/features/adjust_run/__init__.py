"""Vertical slice for the `AdjustRun` command (Phase 6j).

Module-as-namespace surface, symmetric with the other Run slices:

    from cora.run.features import adjust_run

    cmd = adjust_run.AdjustRun(
        run_id=...,
        parameter_patch={"energy_kev": 13.0},
        reason="re-centering ROI on detected feature",
    )
    handler = adjust_run.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.adjust_run import tool
from cora.run.features.adjust_run.command import AdjustRun
from cora.run.features.adjust_run.context import RunAdjustContext
from cora.run.features.adjust_run.decider import decide
from cora.run.features.adjust_run.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.run.features.adjust_run.route import router

__all__ = [
    "AdjustRun",
    "Handler",
    "IdempotentHandler",
    "RunAdjustContext",
    "bind",
    "decide",
    "router",
    "tool",
]
