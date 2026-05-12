"""The `list_actors` query slice.

Cursor-paginated list of actors backed by the
`proj_access_actor_summary` read model that the projection worker
keeps up-to-date. Read-only; no events emitted.
"""

from cora.access.features.list_actors.handler import (
    ActorListPage,
    ActorSummaryItem,
    Handler,
    bind,
)
from cora.access.features.list_actors.query import ListActors
from cora.access.features.list_actors.route import router

__all__ = [
    "ActorListPage",
    "ActorSummaryItem",
    "Handler",
    "ListActors",
    "bind",
    "router",
]
