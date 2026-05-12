"""Vertical slice for the `TruncateRun` command.

Module-as-namespace surface:

    from cora.run.features import truncate_run

    cmd = truncate_run.TruncateRun(
        run_id=...,
        reason="power loss to beamline 32-ID at ~03:14 UTC",
        interrupted_at=datetime(2026, 5, 9, 3, 14, tzinfo=UTC),
    )
    handler = truncate_run.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.truncate_run import tool
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.features.truncate_run.decider import decide
from cora.run.features.truncate_run.handler import Handler, bind
from cora.run.features.truncate_run.route import router

__all__ = [
    "Handler",
    "TruncateRun",
    "bind",
    "decide",
    "router",
    "tool",
]
