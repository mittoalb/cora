"""Application handler for the `list_capabilities` query slice.

Reads `proj_equipment_capability_summary` directly via `deps.pool`.
Single optional `status` filter plus cursor pagination, using the
`$N::text IS NULL OR column = $N` declarative pattern (same as
`list_subjects` / `list_assets`).

`version_tag` flows through to the result row (nullable: only set
once `CapabilityVersioned` has folded; preserved on Deprecated).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.list_capabilities.query import ListCapabilities
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor

_QUERY_NAME = "ListCapabilities"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class CapabilitySummaryItem:
    """One row from the capability projection."""

    capability_id: UUID
    name: str
    status: str
    version_tag: str | None
    created_at: datetime


@dataclass(frozen=True)
class CapabilityListPage:
    """A page of capability summaries plus the cursor for the next page."""

    items: list[CapabilitySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_capabilities handler implements."""

    async def __call__(
        self,
        query: ListCapabilities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> CapabilityListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT capability_id, name, status, version_tag, created_at
FROM proj_equipment_capability_summary
WHERE ($2::text IS NULL OR status = $2)
ORDER BY created_at ASC, capability_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT capability_id, name, status, version_tag, created_at
FROM proj_equipment_capability_summary
WHERE ($2::text IS NULL OR status = $2)
  AND (created_at, capability_id) > ($3, $4)
ORDER BY created_at ASC, capability_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_capabilities handler closed over the shared deps."""

    async def handler(
        query: ListCapabilities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> CapabilityListPage:
        _log.info(
            "list_capabilities.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
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
                "list_capabilities.denied",
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
                "list_capabilities.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return CapabilityListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            CapabilitySummaryItem(
                capability_id=row["capability_id"],
                name=str(row["name"]),
                status=str(row["status"]),
                version_tag=(str(row["version_tag"]) if row["version_tag"] is not None else None),
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.capability_id,
            )

        _log.info(
            "list_capabilities.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return CapabilityListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "CapabilityListPage",
    "CapabilitySummaryItem",
    "Handler",
    "bind",
]
