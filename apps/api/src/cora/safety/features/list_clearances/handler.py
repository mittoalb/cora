"""Application handler for the `list_clearances` query slice.

Reads `proj_safety_clearance_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Eight
optional filters: four scalar (`kind` / `status` / `risk_band` /
`facility_asset_id`) plus four array-membership over the
per-category GIN-indexed binding-id arrays (`binds_to_subject_id`
matches `subject_binding_ids`, and likewise for asset / run /
procedure). Cursor pagination keyed on `(registered_at,
clearance_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per [[project_authz_future]] watch items).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import (
    ArrayContainsFilter,
    ScalarFilter,
    make_list_query_handler,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.errors import UnauthorizedError
from cora.safety.features.list_clearances.query import ListClearances


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
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage: ...


_SELECT_COLUMNS = (
    "clearance_id, kind, facility_asset_id, title, external_id, status, risk_band, "
    "subject_binding_ids, asset_binding_ids, run_binding_ids, procedure_binding_ids, "
    "parent_clearance_id, registered_at, "
    "last_status_changed_at, last_status_reason, last_reviewed_by_actor_id, "
    "valid_from, valid_until, next_review_due_at"
)


def _row_to_item(row: Any) -> ClearanceSummaryItem:
    return ClearanceSummaryItem(
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
            str(row["last_status_reason"]) if row["last_status_reason"] is not None else None
        ),
        last_reviewed_by_actor_id=row["last_reviewed_by_actor_id"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        next_review_due_at=row["next_review_due_at"],
    )


def _log_fields(query: ListClearances) -> dict[str, Any]:
    return {
        "kind": query.kind,
        "status": query.status,
        "risk_band": query.risk_band,
        "facility_asset_id": (str(query.facility_asset_id) if query.facility_asset_id else None),
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_clearances handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListClearances",
        log_prefix="list_clearances",
        unauthorized_error=UnauthorizedError,
        table="proj_safety_clearance_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="clearance_id",
        filters=[
            ScalarFilter(attr="kind"),
            ScalarFilter(attr="status"),
            ScalarFilter(attr="risk_band"),
            ScalarFilter(attr="facility_asset_id"),
            ArrayContainsFilter(attr="binds_to_subject_id", column="subject_binding_ids"),
            ArrayContainsFilter(attr="binds_to_asset_id", column="asset_binding_ids"),
            ArrayContainsFilter(attr="binds_to_run_id", column="run_binding_ids"),
            ArrayContainsFilter(attr="binds_to_procedure_id", column="procedure_binding_ids"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.clearance_id,
        page_from=lambda items, next_cursor: ClearanceListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "ClearanceListPage",
    "ClearanceSummaryItem",
    "Handler",
    "bind",
]
