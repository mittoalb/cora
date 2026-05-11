"""Vertical slice for the `GetRun` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.run.features import get_run

    q = get_run.GetRun(run_id=...)
    handler = get_run.bind(deps)
    run = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.run.features.get_run import tool
from cora.run.features.get_run.handler import Handler, bind
from cora.run.features.get_run.query import GetRun
from cora.run.features.get_run.route import router

__all__ = [
    "GetRun",
    "Handler",
    "bind",
    "router",
    "tool",
]
