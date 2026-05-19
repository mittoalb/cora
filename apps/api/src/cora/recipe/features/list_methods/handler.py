"""Application handler for the `list_methods` query slice.

Reads `proj_recipe_method_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Single optional `status` filter plus cursor pagination on
`(created_at, method_id)`.

`version_tag` flows through to the result row (nullable: only set
once `MethodVersioned` has folded; preserved on Deprecated).

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
from cora.recipe.features.list_methods.query import ListMethods

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class MethodSummaryItem:
    """One row from the method projection.

    `parameters_schema_present` reflects whether the most recent
    `MethodParametersSchemaUpdated` event for this Method carried a
    non-NULL parameters_schema (Phase 6g-a). Default FALSE on legacy
    rows + on Methods that have never had `update_method_parameters_schema`
    called. The schema content itself is not in this projection (load
    on demand via `get_method`).
    """

    method_id: UUID
    name: str
    status: str
    version_tag: str | None
    created_at: datetime
    parameters_schema_present: bool


@dataclass(frozen=True)
class MethodListPage:
    """A page of method summaries plus the cursor for the next page."""

    items: list[MethodSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_methods handler implements."""

    async def __call__(
        self,
        query: ListMethods,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> MethodListPage: ...


_SELECT_COLUMNS = "method_id, name, status, version_tag, created_at, parameters_schema_present"


def _row_to_item(row: Any) -> MethodSummaryItem:
    return MethodSummaryItem(
        method_id=row["method_id"],
        name=str(row["name"]),
        status=str(row["status"]),
        version_tag=str(row["version_tag"]) if row["version_tag"] is not None else None,
        created_at=row["created_at"],
        parameters_schema_present=bool(row["parameters_schema_present"]),
    )


def _log_fields(query: ListMethods) -> dict[str, Any]:
    return {"status": query.status}


def bind(deps: Kernel) -> Handler:
    """Build a list_methods handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListMethods",
        log_prefix="list_methods",
        unauthorized_error=UnauthorizedError,
        table="proj_recipe_method_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="method_id",
        filters=[ScalarFilter(attr="status")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.method_id,
        page_from=lambda items, next_cursor: MethodListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "MethodListPage",
    "MethodSummaryItem",
    "bind",
]
