"""Vertical slice for the `DeactivateActor` command.

Module-as-namespace surface:

    from cora.access.features import deactivate_actor

    cmd = deactivate_actor.DeactivateActor(actor_id=...)
    handler = deactivate_actor.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.access.features.deactivate_actor import tool
from cora.access.features.deactivate_actor.command import DeactivateActor
from cora.access.features.deactivate_actor.decider import decide
from cora.access.features.deactivate_actor.handler import Handler, bind
from cora.access.features.deactivate_actor.route import router

__all__ = [
    "DeactivateActor",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
