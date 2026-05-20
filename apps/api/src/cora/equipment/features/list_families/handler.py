"""Application handler for the `list_families` query slice.

Reads `proj_equipment_family_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Single optional `status` filter plus cursor pagination on
`(created_at, family_id)`.

`version_tag` flows through to the result row (nullable: only set
once `FamilyVersioned` has folded; preserved on Deprecated).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.list_families.query import FamilyStatusFilter, ListFamilies
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class FamilySummaryItem:
    """One row from the family projection."""

    family_id: UUID
    name: str
    status: FamilyStatusFilter
    version_tag: str | None
    created_at: datetime


@dataclass(frozen=True)
class FamilyListPage:
    """A page of family summaries plus the cursor for the next page."""

    items: list[FamilySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_families handler implements."""

    async def __call__(
        self,
        query: ListFamilies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> FamilyListPage: ...


_SELECT_COLUMNS = "family_id, name, status, version_tag, created_at"


def _row_to_item(row: Any) -> FamilySummaryItem:
    return FamilySummaryItem(
        family_id=row["family_id"],
        name=str(row["name"]),
        status=cast("FamilyStatusFilter", str(row["status"])),
        version_tag=str(row["version_tag"]) if row["version_tag"] is not None else None,
        created_at=row["created_at"],
    )


def _log_fields(query: ListFamilies) -> dict[str, Any]:
    return {"status": query.status}


def bind(deps: Kernel) -> Handler:
    """Build a list_families handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListFamilies",
        log_prefix="list_families",
        unauthorized_error=UnauthorizedError,
        table="proj_equipment_family_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="family_id",
        filters=[ScalarFilter(attr="status")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.family_id,
        page_from=lambda items, next_cursor: FamilyListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "FamilyListPage",
    "FamilySummaryItem",
    "Handler",
    "bind",
]
