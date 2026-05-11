"""Vertical slice for the `StopRun` command.

Module-as-namespace surface:

    from cora.run.features import stop_run

    cmd = stop_run.StopRun(run_id=..., reason="hit time budget cleanly")
    handler = stop_run.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.stop_run import tool
from cora.run.features.stop_run.command import StopRun
from cora.run.features.stop_run.decider import decide
from cora.run.features.stop_run.handler import Handler, bind
from cora.run.features.stop_run.route import router

__all__ = [
    "Handler",
    "StopRun",
    "bind",
    "decide",
    "router",
    "tool",
]
