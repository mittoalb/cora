"""Vertical slice for the `StartRun` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.run.features import start_run

    cmd = start_run.StartRun(name="...", plan_id=..., subject_id=...)
    handler = start_run.bind(deps)
    run_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.start_run import tool
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.context import RunStartContext
from cora.run.features.start_run.decider import decide
from cora.run.features.start_run.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.run.features.start_run.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RunStartContext",
    "StartRun",
    "bind",
    "decide",
    "router",
    "tool",
]
