"""Application handler for the `list_runs` query slice.

Reads `proj_run_summary` directly via `deps.pool`. Two optional
filters (status + plan_id) plus cursor pagination, using the
`$N::text IS NULL OR column = $N` declarative pattern (same as
`list_practices` / `list_plans`).

`subject_id` and `raid` flow through to the result row from the
genesis event; both are nullable (Plan-only Runs without a Subject;
ISO-23527 RAiD optional).

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
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs.query import ListRuns

_QUERY_NAME = "ListRuns"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class RunSummaryItem:
    """One row from the run projection."""

    run_id: UUID
    name: str
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None
    status: str
    created_at: datetime


@dataclass(frozen=True)
class RunListPage:
    """A page of run summaries plus the cursor for the next page."""

    items: list[RunSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_runs handler implements."""

    async def __call__(
        self,
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> RunListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT run_id, name, plan_id, subject_id, raid, status, created_at
FROM proj_run_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::uuid IS NULL OR plan_id = $3)
ORDER BY created_at ASC, run_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT run_id, name, plan_id, subject_id, raid, status, created_at
FROM proj_run_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::uuid IS NULL OR plan_id = $3)
  AND (created_at, run_id) > ($4, $5)
ORDER BY created_at ASC, run_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_runs handler closed over the shared deps."""

    async def handler(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> RunListPage:
        _log.info(
            "list_runs.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            status=query.status,
            plan_id=str(query.plan_id) if query.plan_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_runs.denied",
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
                "list_runs.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return RunListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.plan_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.plan_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            RunSummaryItem(
                run_id=row["run_id"],
                name=str(row["name"]),
                plan_id=row["plan_id"],
                subject_id=row["subject_id"],
                raid=str(row["raid"]) if row["raid"] is not None else None,
                status=str(row["status"]),
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.run_id,
            )

        _log.info(
            "list_runs.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return RunListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "RunListPage",
    "RunSummaryItem",
    "bind",
]
