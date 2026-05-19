"""Application handler for the `list_actors` query slice.

Reads `proj_access_actor_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Single optional `status` filter plus cursor pagination on
`(created_at, actor_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.access.errors import UnauthorizedError
from cora.access.features.list_actors.query import ListActors
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class ActorSummaryItem:
    """One row from the actor projection."""

    actor_id: UUID
    name: str
    kind: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class ActorListPage:
    """A page of actor summaries plus the cursor for the next page."""

    items: list[ActorSummaryItem]
    next_cursor: str | None
    """Opaque cursor for the next page; None when no more pages.
    Sticking with the JSON:API cursor profile shape (single nullable
    field) over Stripe's `has_more` boolean — both are defensible per
    research, this is one fewer field to plumb through clients."""


class Handler(Protocol):
    """Callable interface every list_actors handler implements."""

    async def __call__(
        self,
        query: ListActors,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> ActorListPage: ...


_SELECT_COLUMNS = "actor_id, name, kind, status, created_at"


def _row_to_item(row: Any) -> ActorSummaryItem:
    return ActorSummaryItem(
        actor_id=row["actor_id"],
        name=str(row["name"]),
        kind=str(row["kind"]),
        status=str(row["status"]),
        created_at=row["created_at"],
    )


def _log_fields(query: ListActors) -> dict[str, Any]:
    return {"status": query.status}


def bind(deps: Kernel) -> Handler:
    """Build a list_actors handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListActors",
        log_prefix="list_actors",
        unauthorized_error=UnauthorizedError,
        table="proj_access_actor_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="actor_id",
        filters=[ScalarFilter(attr="status")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.actor_id,
        page_from=lambda items, next_cursor: ActorListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "ActorListPage",
    "ActorSummaryItem",
    "Handler",
    "bind",
]
