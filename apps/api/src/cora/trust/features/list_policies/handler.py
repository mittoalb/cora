"""Application handler for the `list_policies` query slice.

Reads `proj_trust_policy_summary` directly via `deps.pool`. Single
optional `conduit_id` filter plus cursor pagination, using the
`$N::uuid IS NULL OR column = $N` declarative pattern.

The list-typed `permitted_principals` and `permitted_commands`
fields are NOT in the projection (and therefore not in the result
row); a future `proj_trust_policy_principals` join projection will
cover "list policies allowing Principal X" if that use case
crystallizes.

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
from cora.trust.features.list_policies.query import ListPolicies

_QUERY_NAME = "ListPolicies"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class PolicySummaryItem:
    """One row from the policy projection."""

    policy_id: UUID
    name: str
    conduit_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class PolicyListPage:
    """A page of policy summaries plus the cursor for the next page."""

    items: list[PolicySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_policies handler implements."""

    async def __call__(
        self,
        query: ListPolicies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> PolicyListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT policy_id, name, conduit_id, created_at
FROM proj_trust_policy_summary
WHERE ($2::uuid IS NULL OR conduit_id = $2)
ORDER BY created_at ASC, policy_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT policy_id, name, conduit_id, created_at
FROM proj_trust_policy_summary
WHERE ($2::uuid IS NULL OR conduit_id = $2)
  AND (created_at, policy_id) > ($3, $4)
ORDER BY created_at ASC, policy_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_policies handler closed over the shared deps."""

    async def handler(
        query: ListPolicies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> PolicyListPage:
        _log.info(
            "list_policies.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            conduit_id=str(query.conduit_id) if query.conduit_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_policies.denied",
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
                "list_policies.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return PolicyListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.conduit_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.conduit_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            PolicySummaryItem(
                policy_id=row["policy_id"],
                name=str(row["name"]),
                conduit_id=row["conduit_id"],
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.policy_id,
            )

        _log.info(
            "list_policies.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return PolicyListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "PolicyListPage",
    "PolicySummaryItem",
    "bind",
]
