"""Vertical slice for the `DefineConduit` command.

Module-as-namespace surface: callers import this slice and use the
short names from the slice's namespace.

    from cora.trust.features import define_conduit

    cmd = define_conduit.DefineConduit(
        name="Detector-to-Storage",
        source_zone_id=...,
        target_zone_id=...,
    )
    handler = define_conduit.bind(deps)
    conduit_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.trust.features.define_conduit import tool
from cora.trust.features.define_conduit.command import DefineConduit
from cora.trust.features.define_conduit.decider import decide
from cora.trust.features.define_conduit.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.trust.features.define_conduit.route import router

__all__ = [
    "DefineConduit",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
