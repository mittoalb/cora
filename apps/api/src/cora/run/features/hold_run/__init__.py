"""Vertical slice for the `HoldRun` command.

Module-as-namespace surface:

    from cora.run.features import hold_run

    cmd = hold_run.HoldRun(run_id=...)
    handler = hold_run.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.hold_run import tool
from cora.run.features.hold_run.command import HoldRun
from cora.run.features.hold_run.decider import decide
from cora.run.features.hold_run.handler import Handler, bind
from cora.run.features.hold_run.route import router

__all__ = [
    "Handler",
    "HoldRun",
    "bind",
    "decide",
    "router",
    "tool",
]
