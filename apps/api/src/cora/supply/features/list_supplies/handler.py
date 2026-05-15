"""Application handler for the `list_supplies` query slice.

Reads `proj_supply_summary` directly via `deps.pool`. Three optional
filters (scope / kind / status), each via the declarative
`$N::text IS NULL OR column = $N` pattern (same as `list_capabilities`
/ `list_subjects` / `list_assets`).

`last_status_changed_at` / `last_status_reason` / `last_trigger`
flow through to the result row: nullable until the supply transitions
(Unknown -> Available or beyond). Useful at list time for ops queries
like "show me supplies that went Available recently and why".

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
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
from cora.supply.errors import UnauthorizedError
from cora.supply.features.list_supplies.query import ListSupplies

_QUERY_NAME = "ListSupplies"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class SupplySummaryItem:
    """One row from the supply projection."""

    supply_id: UUID
    scope: str
    kind: str
    name: str
    status: str
    registered_at: datetime
    last_status_changed_at: datetime | None
    last_status_reason: str | None
    last_trigger: str | None


@dataclass(frozen=True)
class SupplyListPage:
    """A page of supply summaries plus the cursor for the next page."""

    items: list[SupplySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_supplies handler implements."""

    async def __call__(
        self,
        query: ListSupplies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> SupplyListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT supply_id, scope, kind, name, status, registered_at,
       last_status_changed_at, last_status_reason, last_trigger
FROM proj_supply_summary
WHERE ($2::text IS NULL OR scope = $2)
  AND ($3::text IS NULL OR kind = $3)
  AND ($4::text IS NULL OR status = $4)
ORDER BY registered_at ASC, supply_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT supply_id, scope, kind, name, status, registered_at,
       last_status_changed_at, last_status_reason, last_trigger
FROM proj_supply_summary
WHERE ($2::text IS NULL OR scope = $2)
  AND ($3::text IS NULL OR kind = $3)
  AND ($4::text IS NULL OR status = $4)
  AND (registered_at, supply_id) > ($5, $6)
ORDER BY registered_at ASC, supply_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_supplies handler closed over the shared deps."""

    async def handler(
        query: ListSupplies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> SupplyListPage:
        _log.info(
            "list_supplies.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            scope=query.scope,
            kind=query.kind,
            status=query.status,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_supplies.denied",
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
                "list_supplies.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return SupplyListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.scope,
                    query.kind,
                    query.status,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.scope,
                    query.kind,
                    query.status,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            SupplySummaryItem(
                supply_id=row["supply_id"],
                scope=str(row["scope"]),
                kind=str(row["kind"]),
                name=str(row["name"]),
                status=str(row["status"]),
                registered_at=row["registered_at"],
                last_status_changed_at=row["last_status_changed_at"],
                last_status_reason=(
                    str(row["last_status_reason"])
                    if row["last_status_reason"] is not None
                    else None
                ),
                last_trigger=(
                    str(row["last_trigger"]) if row["last_trigger"] is not None else None
                ),
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.registered_at,
                item_id=last.supply_id,
            )

        _log.info(
            "list_supplies.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return SupplyListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "SupplyListPage",
    "SupplySummaryItem",
    "bind",
]
