"""Application handler for the `list_plans` query slice.

Reads `proj_recipe_plan_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Two
optional filters (status + practice_id) plus cursor pagination on
`(created_at, plan_id)`.

`practice_id` and `method_id` flow through to the result row;
`version_tag` is nullable (only set once `PlanVersioned` has folded;
preserved on Deprecated).

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
from cora.recipe.features.list_plans.query import ListPlans

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class PlanSummaryItem:
    """One row from the plan projection.

    `default_parameters_present` reflects whether the most recent
    `PlanDefaultParametersUpdated` event for this Plan carried a
    non-empty default_parameters dict (Phase 6g-b). Default FALSE on
    legacy rows + on Plans that have never had
    `update_plan_default_parameters` called. The defaults dict
    itself is not in this projection (load on demand via `get_plan`).
    """

    plan_id: UUID
    name: str
    practice_id: UUID
    method_id: UUID
    status: str
    version_tag: str | None
    created_at: datetime
    default_parameters_present: bool


@dataclass(frozen=True)
class PlanListPage:
    """A page of plan summaries plus the cursor for the next page."""

    items: list[PlanSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_plans handler implements."""

    async def __call__(
        self,
        query: ListPlans,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> PlanListPage: ...


_SELECT_COLUMNS = (
    "plan_id, name, practice_id, method_id, status, version_tag, created_at, "
    "default_parameters_present"
)


def _row_to_item(row: Any) -> PlanSummaryItem:
    return PlanSummaryItem(
        plan_id=row["plan_id"],
        name=str(row["name"]),
        practice_id=row["practice_id"],
        method_id=row["method_id"],
        status=str(row["status"]),
        version_tag=str(row["version_tag"]) if row["version_tag"] is not None else None,
        created_at=row["created_at"],
        default_parameters_present=bool(row["default_parameters_present"]),
    )


def _log_fields(query: ListPlans) -> dict[str, Any]:
    return {
        "status": query.status,
        "practice_id": str(query.practice_id) if query.practice_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_plans handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListPlans",
        log_prefix="list_plans",
        unauthorized_error=UnauthorizedError,
        table="proj_recipe_plan_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="plan_id",
        filters=[
            ScalarFilter(attr="status"),
            ScalarFilter(attr="practice_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.plan_id,
        page_from=lambda items, next_cursor: PlanListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "PlanListPage",
    "PlanSummaryItem",
    "bind",
]
