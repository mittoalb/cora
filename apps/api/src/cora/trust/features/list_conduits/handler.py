"""Application handler for the `list_conduits` query slice.

Reads `proj_trust_conduit_summary` directly via `deps.pool`. Two
optional UUID filters (source_zone_id + target_zone_id) plus cursor
pagination, using the `$N::uuid IS NULL OR column = $N` declarative
pattern.

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
from cora.trust.features.list_conduits.query import ListConduits

_QUERY_NAME = "ListConduits"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


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
    ) -> ConduitListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT conduit_id, name, source_zone_id, target_zone_id, created_at
FROM proj_trust_conduit_summary
WHERE ($2::uuid IS NULL OR source_zone_id = $2)
  AND ($3::uuid IS NULL OR target_zone_id = $3)
ORDER BY created_at ASC, conduit_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT conduit_id, name, source_zone_id, target_zone_id, created_at
FROM proj_trust_conduit_summary
WHERE ($2::uuid IS NULL OR source_zone_id = $2)
  AND ($3::uuid IS NULL OR target_zone_id = $3)
  AND (created_at, conduit_id) > ($4, $5)
ORDER BY created_at ASC, conduit_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_conduits handler closed over the shared deps."""

    async def handler(
        query: ListConduits,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ConduitListPage:
        _log.info(
            "list_conduits.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            source_zone_id=str(query.source_zone_id) if query.source_zone_id else None,
            target_zone_id=str(query.target_zone_id) if query.target_zone_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_conduits.denied",
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
                "list_conduits.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return ConduitListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.source_zone_id,
                    query.target_zone_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.source_zone_id,
                    query.target_zone_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            ConduitSummaryItem(
                conduit_id=row["conduit_id"],
                name=str(row["name"]),
                source_zone_id=row["source_zone_id"],
                target_zone_id=row["target_zone_id"],
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.conduit_id,
            )

        _log.info(
            "list_conduits.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return ConduitListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "ConduitListPage",
    "ConduitSummaryItem",
    "Handler",
    "bind",
]
