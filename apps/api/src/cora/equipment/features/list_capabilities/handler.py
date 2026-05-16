"""Application handler for the `list_capabilities` query slice.

Reads `proj_equipment_capability_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Single optional `status` filter plus cursor pagination on
`(created_at, capability_id)`.

`version_tag` flows through to the result row (nullable: only set
once `CapabilityVersioned` has folded; preserved on Deprecated).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.list_capabilities.query import ListCapabilities
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler


@dataclass(frozen=True)
class CapabilitySummaryItem:
    """One row from the capability projection."""

    capability_id: UUID
    name: str
    status: str
    version_tag: str | None
    created_at: datetime


@dataclass(frozen=True)
class CapabilityListPage:
    """A page of capability summaries plus the cursor for the next page."""

    items: list[CapabilitySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_capabilities handler implements."""

    async def __call__(
        self,
        query: ListCapabilities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> CapabilityListPage: ...


_SELECT_COLUMNS = "capability_id, name, status, version_tag, created_at"


def _row_to_item(row: Any) -> CapabilitySummaryItem:
    return CapabilitySummaryItem(
        capability_id=row["capability_id"],
        name=str(row["name"]),
        status=str(row["status"]),
        version_tag=str(row["version_tag"]) if row["version_tag"] is not None else None,
        created_at=row["created_at"],
    )


def _log_fields(query: ListCapabilities) -> dict[str, Any]:
    return {"status": query.status}


def bind(deps: Kernel) -> Handler:
    """Build a list_capabilities handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListCapabilities",
        log_prefix="list_capabilities",
        unauthorized_error=UnauthorizedError,
        table="proj_equipment_capability_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="capability_id",
        filters=[ScalarFilter(attr="status")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.capability_id,
        page_from=lambda items, next_cursor: CapabilityListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "CapabilityListPage",
    "CapabilitySummaryItem",
    "Handler",
    "bind",
]
