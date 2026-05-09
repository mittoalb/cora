"""Vertical slice for the `GetActor` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.access.features import get_actor

    q = get_actor.GetActor(actor_id=...)
    handler = get_actor.bind(deps)
    actor = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.access.features.get_actor import tool
from cora.access.features.get_actor.handler import Handler, bind
from cora.access.features.get_actor.query import GetActor
from cora.access.features.get_actor.route import router

__all__ = [
    "GetActor",
    "Handler",
    "bind",
    "router",
    "tool",
]
