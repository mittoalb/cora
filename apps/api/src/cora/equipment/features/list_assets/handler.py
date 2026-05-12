"""Application handler for the `list_assets` query slice.

Reads `proj_equipment_asset_summary` directly via `deps.pool`.
Three optional filters (level, lifecycle, parent_id) plus cursor
pagination. The conditional WHERE pattern uses `$N::text IS NULL OR
column = $N` for enum filters and `$N::uuid IS NULL OR parent_id = $N`
for the UUID filter — keeps the SQL declarative without dynamic
WHERE construction.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.list_assets.query import ListAssets
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor

_QUERY_NAME = "ListAssets"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class AssetSummaryItem:
    """One row from the asset projection."""

    asset_id: UUID
    name: str
    level: str
    lifecycle: str
    parent_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class AssetListPage:
    """A page of asset summaries plus the cursor for the next page."""

    items: list[AssetSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_assets handler implements."""

    async def __call__(
        self,
        query: ListAssets,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> AssetListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT asset_id, name, level, lifecycle, parent_id, created_at
FROM proj_equipment_asset_summary
WHERE ($2::text IS NULL OR level = $2)
  AND ($3::text IS NULL OR lifecycle = $3)
  AND ($4::uuid IS NULL OR parent_id = $4)
ORDER BY created_at ASC, asset_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT asset_id, name, level, lifecycle, parent_id, created_at
FROM proj_equipment_asset_summary
WHERE ($2::text IS NULL OR level = $2)
  AND ($3::text IS NULL OR lifecycle = $3)
  AND ($4::uuid IS NULL OR parent_id = $4)
  AND (created_at, asset_id) > ($5, $6)
ORDER BY created_at ASC, asset_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_assets handler closed over the shared deps."""

    async def handler(
        query: ListAssets,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> AssetListPage:
        _log.info(
            "list_assets.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            level=query.level,
            lifecycle=query.lifecycle,
            parent_id=str(query.parent_id) if query.parent_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_assets.denied",
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
                "list_assets.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return AssetListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.level,
                    query.lifecycle,
                    query.parent_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.level,
                    query.lifecycle,
                    query.parent_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            AssetSummaryItem(
                asset_id=row["asset_id"],
                name=str(row["name"]),
                level=str(row["level"]),
                lifecycle=str(row["lifecycle"]),
                parent_id=row["parent_id"],
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.asset_id,
            )

        _log.info(
            "list_assets.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return AssetListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "AssetListPage",
    "AssetSummaryItem",
    "Handler",
    "bind",
]
