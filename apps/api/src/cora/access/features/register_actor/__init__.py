"""Vertical slice for the `RegisterActor` command.

Module-as-namespace surface: callers import this slice and use the
short names from the slice's namespace.

    from cora.access.features import register_actor

    cmd = register_actor.RegisterActor(name="Doga")
    handler = register_actor.bind(deps)
    actor_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.access.features.register_actor import tool
from cora.access.features.register_actor.command import RegisterActor
from cora.access.features.register_actor.decider import decide
from cora.access.features.register_actor.handler import Handler, bind
from cora.access.features.register_actor.route import router

# UnauthorizedError lives in cora.access.errors (BC-level, not
# slice-specific). Import from cora.access if you need to catch it.

__all__ = [
    "Handler",
    "RegisterActor",
    "bind",
    "decide",
    "router",
    "tool",
]
