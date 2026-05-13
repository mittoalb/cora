"""Application handler for the `list_zones` query slice.

Reads `proj_trust_zone_summary` directly via `deps.pool`. No
filters today (Zone has no cross-aggregate refs and lifecycle
status is deferred). Cursor pagination using the standard
`(created_at, zone_id) > ($N, $M)` keyset pattern.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor
from cora.trust.errors import UnauthorizedError
from cora.trust.features.list_zones.query import ListZones

_QUERY_NAME = "ListZones"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


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
    ) -> ZoneListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT zone_id, name, created_at
FROM proj_trust_zone_summary
ORDER BY created_at ASC, zone_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT zone_id, name, created_at
FROM proj_trust_zone_summary
WHERE (created_at, zone_id) > ($2, $3)
ORDER BY created_at ASC, zone_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_zones handler closed over the shared deps."""

    async def handler(
        query: ListZones,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ZoneListPage:
        _log.info(
            "list_zones.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_zones.denied",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        cursor_at: datetime | None = None
        cursor_id: UUID | None = None
        if query.cursor is not None:
            cursor_at, cursor_id = decode_cursor(query.cursor)

        if deps.pool is None:
            _log.info(
                "list_zones.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return ZoneListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            ZoneSummaryItem(
                zone_id=row["zone_id"],
                name=str(row["name"]),
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.zone_id,
            )

        _log.info(
            "list_zones.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return ZoneListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "ZoneListPage",
    "ZoneSummaryItem",
    "bind",
]
