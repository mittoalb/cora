"""Application handler for the `list_practices` query slice.

Reads `proj_recipe_practice_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Two
optional filters (status + method_id) plus cursor pagination on
`(created_at, practice_id)`.

`method_id` and `site_id` flow through to the result row;
`version_tag` is nullable (only set once `PracticeVersioned` has
folded; preserved on Deprecated).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.list_practices.query import ListPractices


@dataclass(frozen=True)
class PracticeSummaryItem:
    """One row from the practice projection."""

    practice_id: UUID
    name: str
    method_id: UUID
    site_id: UUID
    status: str
    version_tag: str | None
    created_at: datetime


@dataclass(frozen=True)
class PracticeListPage:
    """A page of practice summaries plus the cursor for the next page."""

    items: list[PracticeSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_practices handler implements."""

    async def __call__(
        self,
        query: ListPractices,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> PracticeListPage: ...


_SELECT_COLUMNS = "practice_id, name, method_id, site_id, status, version_tag, created_at"


def _row_to_item(row: Any) -> PracticeSummaryItem:
    return PracticeSummaryItem(
        practice_id=row["practice_id"],
        name=str(row["name"]),
        method_id=row["method_id"],
        site_id=row["site_id"],
        status=str(row["status"]),
        version_tag=str(row["version_tag"]) if row["version_tag"] is not None else None,
        created_at=row["created_at"],
    )


def _log_fields(query: ListPractices) -> dict[str, Any]:
    return {
        "status": query.status,
        "method_id": str(query.method_id) if query.method_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_practices handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListPractices",
        log_prefix="list_practices",
        unauthorized_error=UnauthorizedError,
        table="proj_recipe_practice_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="practice_id",
        filters=[
            ScalarFilter(attr="status"),
            ScalarFilter(attr="method_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.practice_id,
        page_from=lambda items, next_cursor: PracticeListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "PracticeListPage",
    "PracticeSummaryItem",
    "bind",
]
