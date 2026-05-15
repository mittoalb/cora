"""Application handler for the `list_procedures` query slice.

Reads `proj_operation_procedure_summary` directly via `deps.pool`.
Four optional filters (status / kind / parent_run_id / target_asset_id),
each via the declarative `$N::<type> IS NULL OR column = $N` pattern
(target_asset_id uses `$N = ANY(target_asset_ids)` to leverage the
GIN index).

`last_status_changed_at` / `last_status_reason` / `interrupted_at` /
`steps_logbook_id` flow through to the result row: nullable until the
respective transition / lazy-open lands.

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
from cora.operation.errors import UnauthorizedError
from cora.operation.features.list_procedures.query import ListProcedures

_QUERY_NAME = "ListProcedures"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class ProcedureSummaryItem:
    """One row from the procedure projection."""

    procedure_id: UUID
    name: str
    kind: str
    target_asset_ids: list[UUID]
    parent_run_id: UUID | None
    status: str
    steps_logbook_id: UUID | None
    registered_at: datetime
    last_status_changed_at: datetime | None
    last_status_reason: str | None
    interrupted_at: datetime | None


@dataclass(frozen=True)
class ProcedureListPage:
    """A page of procedure summaries plus the cursor for the next page."""

    items: list[ProcedureSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_procedures handler implements."""

    async def __call__(
        self,
        query: ListProcedures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ProcedureListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT procedure_id, name, kind, target_asset_ids, parent_run_id, status,
       steps_logbook_id, registered_at,
       last_status_changed_at, last_status_reason, interrupted_at
FROM proj_operation_procedure_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::text IS NULL OR kind = $3)
  AND ($4::uuid IS NULL OR parent_run_id = $4)
  AND ($5::uuid IS NULL OR $5 = ANY(target_asset_ids))
ORDER BY registered_at ASC, procedure_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT procedure_id, name, kind, target_asset_ids, parent_run_id, status,
       steps_logbook_id, registered_at,
       last_status_changed_at, last_status_reason, interrupted_at
FROM proj_operation_procedure_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::text IS NULL OR kind = $3)
  AND ($4::uuid IS NULL OR parent_run_id = $4)
  AND ($5::uuid IS NULL OR $5 = ANY(target_asset_ids))
  AND (registered_at, procedure_id) > ($6, $7)
ORDER BY registered_at ASC, procedure_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_procedures handler closed over the shared deps."""

    async def handler(
        query: ListProcedures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ProcedureListPage:
        _log.info(
            "list_procedures.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            status=query.status,
            kind=query.kind,
            parent_run_id=str(query.parent_run_id) if query.parent_run_id else None,
            target_asset_id=str(query.target_asset_id) if query.target_asset_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_procedures.denied",
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
                "list_procedures.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return ProcedureListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.kind,
                    query.parent_run_id,
                    query.target_asset_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.kind,
                    query.parent_run_id,
                    query.target_asset_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            ProcedureSummaryItem(
                procedure_id=row["procedure_id"],
                name=str(row["name"]),
                kind=str(row["kind"]),
                target_asset_ids=list(row["target_asset_ids"]),
                parent_run_id=row["parent_run_id"],
                status=str(row["status"]),
                steps_logbook_id=row["steps_logbook_id"],
                registered_at=row["registered_at"],
                last_status_changed_at=row["last_status_changed_at"],
                last_status_reason=(
                    str(row["last_status_reason"])
                    if row["last_status_reason"] is not None
                    else None
                ),
                interrupted_at=row["interrupted_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.registered_at,
                item_id=last.procedure_id,
            )

        _log.info(
            "list_procedures.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return ProcedureListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "Handler",
    "ProcedureListPage",
    "ProcedureSummaryItem",
    "bind",
]
