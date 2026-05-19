"""Application handler for the `list_zones` query slice.

Reads `proj_trust_zone_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. No
filters today (Zone has no cross-aggregate refs and lifecycle
status is deferred). Cursor pagination using the standard
`(created_at, zone_id)` keyset.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import make_list_query_handler
from cora.trust.errors import UnauthorizedError
from cora.trust.features.list_zones.query import ListZones

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class ZoneSummaryItem:
    """One row from the zone projection."""

    zone_id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True)
class ZoneListPage:
    """A page of zone summaries plus the cursor for the next page."""

    items: list[ZoneSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_zones handler implements."""

    async def __call__(
        self,
        query: ListZones,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> ZoneListPage: ...


_SELECT_COLUMNS = "zone_id, name, created_at"


def _row_to_item(row: Any) -> ZoneSummaryItem:
    return ZoneSummaryItem(
        zone_id=row["zone_id"],
        name=str(row["name"]),
        created_at=row["created_at"],
    )


def bind(deps: Kernel) -> Handler:
    """Build a list_zones handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListZones",
        log_prefix="list_zones",
        unauthorized_error=UnauthorizedError,
        table="proj_trust_zone_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="zone_id",
        filters=[],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.zone_id,
        page_from=lambda items, next_cursor: ZoneListPage(items=items, next_cursor=next_cursor),
    )


__all__ = [
    "Handler",
    "ZoneListPage",
    "ZoneSummaryItem",
    "bind",
]
