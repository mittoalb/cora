"""Vertical slice for the `DefineZone` command.

Module-as-namespace surface: callers import this slice and use the
short names from the slice's namespace.

    from cora.trust.features import define_zone

    cmd = define_zone.DefineZone(name="Detector")
    handler = define_zone.bind(deps)
    zone_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.trust.features.define_zone import tool
from cora.trust.features.define_zone.command import DefineZone
from cora.trust.features.define_zone.decider import decide
from cora.trust.features.define_zone.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.trust.features.define_zone.route import router

__all__ = [
    "DefineZone",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
