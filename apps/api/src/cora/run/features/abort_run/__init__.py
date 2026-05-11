"""Vertical slice for the `AbortRun` command.

Module-as-namespace surface:

    from cora.run.features import abort_run

    cmd = abort_run.AbortRun(run_id=..., reason="detector overheating")
    handler = abort_run.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.abort_run import tool
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.abort_run.decider import decide
from cora.run.features.abort_run.handler import Handler, bind
from cora.run.features.abort_run.route import router

__all__ = [
    "AbortRun",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
