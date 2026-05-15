"""Application handler for the `list_clearances` query slice.

Reads `proj_safety_clearance_summary` directly via `deps.pool`. 8
optional filters (kind / status / risk_band / facility_asset_id +
4 binds_to_*_id), each via the declarative `$N::<type> IS NULL OR
column = $N` pattern (binds_to_* filters use `$N = ANY(<col>_ids)`
to leverage the per-column GIN index).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per [[project_authz_future]] watch items).
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
from cora.safety.errors import UnauthorizedError
from cora.safety.features.list_clearances.query import ListClearances

_QUERY_NAME = "ListClearances"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class ClearanceSummaryItem:
    """One row from the clearance projection."""

    clearance_id: UUID
    kind: str
    facility_asset_id: UUID
    title: str
    external_id: str | None
    status: str
    risk_band: str | None
    subject_binding_ids: list[UUID]
    asset_binding_ids: list[UUID]
    run_binding_ids: list[UUID]
    procedure_binding_ids: list[UUID]
    parent_clearance_id: UUID | None
    registered_at: datetime
    last_status_changed_at: datetime | None
    last_status_reason: str | None
    last_reviewed_by_actor_id: UUID | None
    valid_from: datetime | None
    valid_until: datetime | None
    next_review_due_at: datetime | None


@dataclass(frozen=True)
class ClearanceListPage:
    """A page of clearance summaries plus the cursor for the next page."""

    items: list[ClearanceSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_clearances handler implements."""

    async def __call__(
        self,
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ClearanceListPage: ...


_SELECT_COLUMNS = """
SELECT clearance_id, kind, facility_asset_id, title, external_id, status,
       risk_band,
       subject_binding_ids, asset_binding_ids, run_binding_ids, procedure_binding_ids,
       parent_clearance_id, registered_at,
       last_status_changed_at, last_status_reason, last_reviewed_by_actor_id,
       valid_from, valid_until, next_review_due_at
"""

_FILTER_CLAUSE = """
WHERE ($2::text IS NULL OR kind = $2)
  AND ($3::text IS NULL OR status = $3)
  AND ($4::text IS NULL OR risk_band = $4)
  AND ($5::uuid IS NULL OR facility_asset_id = $5)
  AND ($6::uuid IS NULL OR $6 = ANY(subject_binding_ids))
  AND ($7::uuid IS NULL OR $7 = ANY(asset_binding_ids))
  AND ($8::uuid IS NULL OR $8 = ANY(run_binding_ids))
  AND ($9::uuid IS NULL OR $9 = ANY(procedure_binding_ids))
"""

_LIST_NO_CURSOR_SQL = (
    _SELECT_COLUMNS
    + "FROM proj_safety_clearance_summary\n"
    + _FILTER_CLAUSE
    + "ORDER BY registered_at ASC, clearance_id ASC\n"
    + "LIMIT $1"
)

_LIST_WITH_CURSOR_SQL = (
    _SELECT_COLUMNS
    + "FROM proj_safety_clearance_summary\n"
    + _FILTER_CLAUSE
    + "  AND (registered_at, clearance_id) > ($10, $11)\n"
    + "ORDER BY registered_at ASC, clearance_id ASC\n"
    + "LIMIT $1"
)


def bind(deps: Kernel) -> Handler:
    """Build a list_clearances handler closed over the shared deps."""

    async def handler(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> ClearanceListPage:
        _log.info(
            "list_clearances.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            kind=query.kind,
            status=query.status,
            risk_band=query.risk_band,
            facility_asset_id=str(query.facility_asset_id) if query.facility_asset_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_clearances.denied",
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
                "list_clearances.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return ClearanceListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.kind,
                    query.status,
                    query.risk_band,
                    query.facility_asset_id,
                    query.binds_to_subject_id,
                    query.binds_to_asset_id,
                    query.binds_to_run_id,
                    query.binds_to_procedure_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.kind,
                    query.status,
                    query.risk_band,
                    query.facility_asset_id,
                    query.binds_to_subject_id,
                    query.binds_to_asset_id,
                    query.binds_to_run_id,
                    query.binds_to_procedure_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            ClearanceSummaryItem(
                clearance_id=row["clearance_id"],
                kind=str(row["kind"]),
                facility_asset_id=row["facility_asset_id"],
                title=str(row["title"]),
                external_id=str(row["external_id"]) if row["external_id"] is not None else None,
                status=str(row["status"]),
                risk_band=str(row["risk_band"]) if row["risk_band"] is not None else None,
                subject_binding_ids=list(row["subject_binding_ids"]),
                asset_binding_ids=list(row["asset_binding_ids"]),
                run_binding_ids=list(row["run_binding_ids"]),
                procedure_binding_ids=list(row["procedure_binding_ids"]),
                parent_clearance_id=row["parent_clearance_id"],
                registered_at=row["registered_at"],
                last_status_changed_at=row["last_status_changed_at"],
                last_status_reason=(
                    str(row["last_status_reason"])
                    if row["last_status_reason"] is not None
                    else None
                ),
                last_reviewed_by_actor_id=row["last_reviewed_by_actor_id"],
                valid_from=row["valid_from"],
                valid_until=row["valid_until"],
                next_review_due_at=row["next_review_due_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.registered_at,
                item_id=last.clearance_id,
            )

        _log.info(
            "list_clearances.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return ClearanceListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "ClearanceListPage",
    "ClearanceSummaryItem",
    "Handler",
    "bind",
]
