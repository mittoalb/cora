"""Application handler for the `list_plans` query slice.

Reads `proj_recipe_plan_summary` directly via `deps.pool`. Two
optional filters (status + practice_id) plus cursor pagination,
using the `$N::text IS NULL OR column = $N` declarative pattern.

`practice_id` and `method_id` flow through to the result row;
`version_tag` is nullable (only set once `PlanVersioned` has folded;
preserved on Deprecated).

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
from cora.recipe.features.list_plans.query import ListPlans

_QUERY_NAME = "ListPlans"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class PlanSummaryItem:
    """One row from the plan projection."""

    plan_id: UUID
    name: str
    practice_id: UUID
    method_id: UUID
    status: str
    version_tag: str | None
    created_at: datetime


@dataclass(frozen=True)
class PlanListPage:
    """A page of plan summaries plus the cursor for the next page."""

    items: list[PlanSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_plans handler implements."""

    async def __call__(
        self,
        query: ListPlans,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> PlanListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT plan_id, name, practice_id, method_id, status, version_tag, created_at
FROM proj_recipe_plan_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::uuid IS NULL OR practice_id = $3)
ORDER BY created_at ASC, plan_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT plan_id, name, practice_id, method_id, status, version_tag, created_at
FROM proj_recipe_plan_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::uuid IS NULL OR practice_id = $3)
  AND (created_at, plan_id) > ($4, $5)
ORDER BY created_at ASC, plan_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_plans handler closed over the shared deps."""

    async def handler(
        query: ListPlans,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> PlanListPage:
        _log.info(
            "list_plans.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            status=query.status,
            practice_id=str(query.practice_id) if query.practice_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_plans.denied",
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
                "list_plans.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return PlanListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.practice_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.practice_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            PlanSummaryItem(
                plan_id=row["plan_id"],
                name=str(row["name"]),
                practice_id=row["practice_id"],
                method_id=row["method_id"],
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
                item_id=last.plan_id,
            )

        _log.info(
            "list_plans.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return PlanListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "PlanListPage",
    "PlanSummaryItem",
    "bind",
]
