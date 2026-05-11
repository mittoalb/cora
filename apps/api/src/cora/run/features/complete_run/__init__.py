"""Vertical slice for the `CompleteRun` command.

Module-as-namespace surface:

    from cora.run.features import complete_run

    cmd = complete_run.CompleteRun(run_id=...)
    handler = complete_run.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.complete_run import tool
from cora.run.features.complete_run.command import CompleteRun
from cora.run.features.complete_run.decider import decide
from cora.run.features.complete_run.handler import Handler, bind
from cora.run.features.complete_run.route import router

__all__ = [
    "CompleteRun",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
