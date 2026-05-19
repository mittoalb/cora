"""Application handler for the `list_conduits` query slice.

Reads `proj_trust_conduit_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Two
optional UUID filters (source_zone_id + target_zone_id) plus
cursor pagination on `(created_at, conduit_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.errors import UnauthorizedError
from cora.trust.features.list_conduits.query import ListConduits


@dataclass(frozen=True)
class ConduitSummaryItem:
    """One row from the conduit projection."""

    conduit_id: UUID
    name: str
    source_zone_id: UUID
    target_zone_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ConduitListPage:
    """A page of conduit summaries plus the cursor for the next page."""

    items: list[ConduitSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_conduits handler implements."""

    async def __call__(
        self,
        query: ListConduits,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConduitListPage: ...


_SELECT_COLUMNS = "conduit_id, name, source_zone_id, target_zone_id, created_at"


def _row_to_item(row: Any) -> ConduitSummaryItem:
    return ConduitSummaryItem(
        conduit_id=row["conduit_id"],
        name=str(row["name"]),
        source_zone_id=row["source_zone_id"],
        target_zone_id=row["target_zone_id"],
        created_at=row["created_at"],
    )


def _log_fields(query: ListConduits) -> dict[str, Any]:
    return {
        "source_zone_id": str(query.source_zone_id) if query.source_zone_id else None,
        "target_zone_id": str(query.target_zone_id) if query.target_zone_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_conduits handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListConduits",
        log_prefix="list_conduits",
        unauthorized_error=UnauthorizedError,
        table="proj_trust_conduit_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="conduit_id",
        filters=[
            ScalarFilter(attr="source_zone_id"),
            ScalarFilter(attr="target_zone_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.conduit_id,
        page_from=lambda items, next_cursor: ConduitListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "ConduitListPage",
    "ConduitSummaryItem",
    "Handler",
    "bind",
]
