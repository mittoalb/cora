"""Application handler for the `list_methods` query slice.

Reads `proj_recipe_method_summary` directly via `deps.pool`. Single
optional `status` filter plus cursor pagination, using the
`$N::text IS NULL OR column = $N` declarative pattern (same as
`list_capabilities` / `list_subjects`).

`version_tag` flows through to the result row (nullable: only set
once `MethodVersioned` has folded; preserved on Deprecated).

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
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.list_methods.query import ListMethods

_QUERY_NAME = "ListMethods"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class MethodSummaryItem:
    """One row from the method projection.

    `parameters_schema_present` reflects whether the most recent
    `MethodParametersSchemaUpdated` event for this Method carried a
    non-NULL parameters_schema (Phase 6g-a). Default FALSE on legacy
    rows + on Methods that have never had `update_method_parameters_schema`
    called. The schema content itself is not in this projection (load
    on demand via `get_method`).
    """

    method_id: UUID
    name: str
    status: str
    version_tag: str | None
    created_at: datetime
    parameters_schema_present: bool


@dataclass(frozen=True)
class MethodListPage:
    """A page of method summaries plus the cursor for the next page."""

    items: list[MethodSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_methods handler implements."""

    async def __call__(
        self,
        query: ListMethods,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> MethodListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT method_id, name, status, version_tag, created_at, parameters_schema_present
FROM proj_recipe_method_summary
WHERE ($2::text IS NULL OR status = $2)
ORDER BY created_at ASC, method_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT method_id, name, status, version_tag, created_at, parameters_schema_present
FROM proj_recipe_method_summary
WHERE ($2::text IS NULL OR status = $2)
  AND (created_at, method_id) > ($3, $4)
ORDER BY created_at ASC, method_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_methods handler closed over the shared deps."""

    async def handler(
        query: ListMethods,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> MethodListPage:
        _log.info(
            "list_methods.start",
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
                "list_methods.denied",
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
                "list_methods.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return MethodListPage(items=[], next_cursor=None)

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
            MethodSummaryItem(
                method_id=row["method_id"],
                name=str(row["name"]),
                status=str(row["status"]),
                version_tag=(str(row["version_tag"]) if row["version_tag"] is not None else None),
                created_at=row["created_at"],
                parameters_schema_present=bool(row["parameters_schema_present"]),
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.method_id,
            )

        _log.info(
            "list_methods.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return MethodListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "MethodListPage",
    "MethodSummaryItem",
    "bind",
]
