"""Application handler for the `list_supplies` query slice.

Reads `proj_supply_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Three
optional filters (scope + kind + status) plus cursor pagination on
`(registered_at, supply_id)`.

`last_status_changed_at` / `last_status_reason` / `last_trigger`
flow through to the result row: nullable until the supply transitions
(Unknown -> Available or beyond). Useful at list time for ops queries
like "show me supplies that went Available recently and why".

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
from cora.supply.errors import UnauthorizedError
from cora.supply.features.list_supplies.query import ListSupplies

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class SupplySummaryItem:
    """One row from the supply projection."""

    supply_id: UUID
    scope: str
    kind: str
    name: str
    status: str
    registered_at: datetime
    last_status_changed_at: datetime | None
    last_status_reason: str | None
    last_trigger: str | None


@dataclass(frozen=True)
class SupplyListPage:
    """A page of supply summaries plus the cursor for the next page."""

    items: list[SupplySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_supplies handler implements."""

    async def __call__(
        self,
        query: ListSupplies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> SupplyListPage: ...


_SELECT_COLUMNS = (
    "supply_id, scope, kind, name, status, registered_at, "
    "last_status_changed_at, last_status_reason, last_trigger"
)


def _row_to_item(row: Any) -> SupplySummaryItem:
    return SupplySummaryItem(
        supply_id=row["supply_id"],
        scope=str(row["scope"]),
        kind=str(row["kind"]),
        name=str(row["name"]),
        status=str(row["status"]),
        registered_at=row["registered_at"],
        last_status_changed_at=row["last_status_changed_at"],
        last_status_reason=(
            str(row["last_status_reason"]) if row["last_status_reason"] is not None else None
        ),
        last_trigger=str(row["last_trigger"]) if row["last_trigger"] is not None else None,
    )


def _log_fields(query: ListSupplies) -> dict[str, Any]:
    return {
        "scope": query.scope,
        "kind": query.kind,
        "status": query.status,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_supplies handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListSupplies",
        log_prefix="list_supplies",
        unauthorized_error=UnauthorizedError,
        table="proj_supply_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="supply_id",
        filters=[
            ScalarFilter(attr="scope"),
            ScalarFilter(attr="kind"),
            ScalarFilter(attr="status"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.supply_id,
        page_from=lambda items, next_cursor: SupplyListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "SupplyListPage",
    "SupplySummaryItem",
    "bind",
]
