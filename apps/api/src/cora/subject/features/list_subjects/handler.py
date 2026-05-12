"""Application handler for the `list_subjects` query slice.

Same shape as `cora.access.features.list_actors`: keyset on
`(created_at, subject_id)` with `LIMIT $limit + 1` to detect
"is there a next page?". Reads from `proj_subject_summary` via
`deps.pool`; returns an empty page when pool is None (in-memory
test environment) so contract tests using `app_env=test` don't
need Postgres.

BOLA note: the projection has no per-principal scoping today —
every `ListSubjects`-permitted principal sees every subject. Per-
row scoping is deferred-with-trigger pending ReBAC (see
`memory/project_deferred.md` "BOLA per-row scoping for list
endpoints"). The contract test in
`tests/contract/test_cross_principal_bola.py` exercises the
WEAKER defense available today: command-name gating denies non-
permitted principals at the route boundary with 403.
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
from cora.subject.errors import UnauthorizedError
from cora.subject.features.list_subjects.query import ListSubjects

_QUERY_NAME = "ListSubjects"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class SubjectSummaryItem:
    """One row from the subject projection."""

    subject_id: UUID
    name: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class SubjectListPage:
    """A page of subject summaries plus the cursor for the next page."""

    items: list[SubjectSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_subjects handler implements."""

    async def __call__(
        self,
        query: ListSubjects,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> SubjectListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT subject_id, name, status, created_at
FROM proj_subject_summary
WHERE ($2::text IS NULL OR status = $2)
ORDER BY created_at ASC, subject_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT subject_id, name, status, created_at
FROM proj_subject_summary
WHERE ($2::text IS NULL OR status = $2)
  AND (created_at, subject_id) > ($3, $4)
ORDER BY created_at ASC, subject_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_subjects handler closed over the shared deps."""

    async def handler(
        query: ListSubjects,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> SubjectListPage:
        _log.info(
            "list_subjects.start",
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
                "list_subjects.denied",
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
                "list_subjects.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return SubjectListPage(items=[], next_cursor=None)

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
            SubjectSummaryItem(
                subject_id=row["subject_id"],
                name=str(row["name"]),
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
                item_id=last.subject_id,
            )

        _log.info(
            "list_subjects.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return SubjectListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "SubjectListPage",
    "SubjectSummaryItem",
    "bind",
]
