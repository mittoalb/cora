"""Application handler for the `list_clearance_templates` query slice.

Reads `proj_safety_clearance_template_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Three
optional filters (facility_code + status + code) plus cursor pagination
on `(defined_at, template_id)`.

`version` flows through to the result row (default 1). `supersedes_template_id`
flows through (nullable: only set when the template is the result of
version_clearance_template).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.errors import UnauthorizedError
from cora.safety.features.list_clearance_templates.query import (
    ClearanceTemplateStatusFilter,
    ListClearanceTemplates,
)


@dataclass(frozen=True)
class ClearanceTemplateSummaryItem:
    """One row from the clearance template projection."""

    template_id: UUID
    code: str
    title: str
    facility_code: str
    version: int
    status: ClearanceTemplateStatusFilter
    defined_at: datetime


@dataclass(frozen=True)
class ClearanceTemplateListPage:
    """A page of clearance template summaries plus the cursor for the next page."""

    items: list[ClearanceTemplateSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_clearance_templates handler implements."""

    async def __call__(
        self,
        query: ListClearanceTemplates,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceTemplateListPage: ...


_SELECT_COLUMNS = "template_id, code, title, facility_code, version, status, defined_at"


def _row_to_item(row: Any) -> ClearanceTemplateSummaryItem:
    return ClearanceTemplateSummaryItem(
        template_id=row["template_id"],
        code=str(row["code"]),
        title=str(row["title"]),
        facility_code=str(row["facility_code"]),
        version=int(row["version"]),
        status=cast("ClearanceTemplateStatusFilter", str(row["status"])),
        defined_at=row["defined_at"],
    )


def _log_fields(query: ListClearanceTemplates) -> dict[str, Any]:
    return {
        "facility_code": query.facility_code,
        "status": query.status,
        "code": query.code,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_clearance_templates handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListClearanceTemplates",
        log_prefix="list_clearance_templates",
        unauthorized_error=UnauthorizedError,
        table="proj_safety_clearance_template_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="defined_at",
        id_column="template_id",
        filters=[
            ScalarFilter(attr="facility_code"),
            ScalarFilter(attr="status"),
            ScalarFilter(attr="code"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.defined_at,
        item_cursor_id=lambda item: item.template_id,
        page_from=lambda items, next_cursor: ClearanceTemplateListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "ClearanceTemplateListPage",
    "ClearanceTemplateSummaryItem",
    "Handler",
    "bind",
]
