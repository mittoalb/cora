"""Application handler for the `list_actors` query slice.

Reads the `proj_access_actor_summary` projection table directly via
the asyncpg pool (no event-stream fold; the worker keeps the
projection up-to-date). Pagination shape: keyset on `(created_at,
actor_id)` with `LIMIT $limit + 1` to detect "is there a next page?";
the last extra row is dropped from `items` and its
`(created_at, actor_id)` becomes `next_cursor`.

BOLA note: the projection has no per-principal scoping today — every
`ListActors`-permitted principal sees every actor. This is a known
gap pending ReBAC (per `memory/project_authz_future.md`); documented
in `project_deferred.md` under "BOLA per-row scoping for list
endpoints (ReBAC dependency)". The contract test in
`tests/contract/test_cross_principal_bola.py` exercises the WEAKER
defense available today: command-name gating denies non-permitted
principals at the route boundary with 403.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.access.errors import UnauthorizedError
from cora.access.features.list_actors.query import ListActors
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor

_QUERY_NAME = "ListActors"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class ActorSummaryItem:
    """One row from the actor projection."""

    actor_id: UUID
    name: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class ActorListPage:
    """A page of actor summaries plus the cursor for the next page."""

    items: list[ActorSummaryItem]
    next_cursor: str | None
    """Opaque cursor for the next page; None when no more pages.
    Sticking with the JSON:API cursor profile shape (single nullable
    field) over Stripe's `has_more` boolean — both are defensible per
    research, this is one fewer field to plumb through clients."""


class Handler(Protocol):
    """Callable interface every list_actors handler implements."""

    async def __call__(
        self,
        query: ListActors,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ActorListPage: ...


# Two SQL shapes: cursor-present uses keyset comparison; cursor-absent
# scans from the start. Status-filter is parameterized in both.
_LIST_NO_CURSOR_SQL = """
SELECT actor_id, name, status, created_at
FROM proj_access_actor_summary
WHERE ($2::text IS NULL OR status = $2)
ORDER BY created_at ASC, actor_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT actor_id, name, status, created_at
FROM proj_access_actor_summary
WHERE ($2::text IS NULL OR status = $2)
  AND (created_at, actor_id) > ($3, $4)
ORDER BY created_at ASC, actor_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_actors handler closed over the shared deps."""

    async def handler(
        query: ListActors,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ActorListPage:
        _log.info(
            "list_actors.start",
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
                "list_actors.denied",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Decode cursor if present. InvalidCursorError propagates to
        # the route layer's exception handler -> 422.
        cursor_at: datetime | None = None
        cursor_id: UUID | None = None
        if query.cursor is not None:
            cursor_at, cursor_id = decode_cursor(query.cursor)

        # Fetch limit+1 to detect "is there another page?".
        if deps.pool is None:
            # In-memory test environment has no projection table; return
            # an empty page so contract tests using `app_env=test` don't
            # need to spin up Postgres just to hit the endpoint.
            _log.info(
                "list_actors.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return ActorListPage(items=[], next_cursor=None)

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

        # Slice + decide next_cursor.
        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            ActorSummaryItem(
                actor_id=row["actor_id"],
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
                item_id=last.actor_id,
            )

        _log.info(
            "list_actors.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return ActorListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "ActorListPage",
    "ActorSummaryItem",
    "Handler",
    "bind",
]
