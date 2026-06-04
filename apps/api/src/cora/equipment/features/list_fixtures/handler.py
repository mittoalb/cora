"""Application handler for the `list_fixtures` query slice.

Reads `proj_equipment_fixture_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Three optional filters (assembly_id, surface_id,
assembly_content_hash), all combinable. Cursor pagination on
`(created_at, fixture_id)`.

Returns SUMMARY rows (counts only: binding_count + override_count).
For the full slot_asset_bindings + parameter_overrides, callers
pivot to get_fixture (per-id event-fold).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.list_fixtures.query import ListFixtures
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class FixtureSummaryItem:
    """One row from the Fixture projection.

    Summary-only: counts (`binding_count`, `override_count`) plus
    metadata. The full slot_asset_bindings + parameter_overrides
    live in the FixtureRegistered event payload; call `get_fixture`
    to load them.
    """

    fixture_id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    binding_count: int
    override_count: int
    created_at: datetime


@dataclass(frozen=True)
class FixtureListPage:
    """A page of Fixture summaries plus the cursor for the next page."""

    items: list[FixtureSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_fixtures handler implements."""

    async def __call__(
        self,
        query: ListFixtures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> FixtureListPage: ...


_SELECT_COLUMNS = (
    "fixture_id, assembly_id, assembly_content_hash, surface_id, "
    "binding_count, override_count, created_at"
)


def _row_to_item(row: Any) -> FixtureSummaryItem:
    return FixtureSummaryItem(
        fixture_id=row["fixture_id"],
        assembly_id=row["assembly_id"],
        assembly_content_hash=str(row["assembly_content_hash"]),
        surface_id=row["surface_id"],
        binding_count=int(row["binding_count"]),
        override_count=int(row["override_count"]),
        created_at=row["created_at"],
    )


def _log_fields(query: ListFixtures) -> dict[str, Any]:
    # Truncate content_hash to a 12-char prefix: the full 64-char SHA-256
    # bloats every list-call log line; the prefix is plenty for triage
    # since collisions across operator-supplied Assemblies are negligible.
    hash_prefix = (
        f"{query.assembly_content_hash[:12]}..."
        if query.assembly_content_hash is not None
        else None
    )
    return {
        "assembly_id": str(query.assembly_id) if query.assembly_id is not None else None,
        "surface_id": str(query.surface_id) if query.surface_id is not None else None,
        "assembly_content_hash_prefix": hash_prefix,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_fixtures handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListFixtures",
        log_prefix="list_fixtures",
        unauthorized_error=UnauthorizedError,
        table="proj_equipment_fixture_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="fixture_id",
        filters=[
            ScalarFilter(attr="assembly_id"),
            ScalarFilter(attr="surface_id"),
            ScalarFilter(attr="assembly_content_hash"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.fixture_id,
        page_from=lambda items, next_cursor: FixtureListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "FixtureListPage",
    "FixtureSummaryItem",
    "Handler",
    "bind",
]
