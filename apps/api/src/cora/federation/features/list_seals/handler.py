"""Application handler for the `list_seals` query slice.

Reads `proj_federation_seal_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. One
optional filter (`status`). Cursor pagination keyed on
`(initialized_at, seal_stream_id)` where `seal_stream_id` is the
projection-stored UUID5 derivation of the row's `facility_id`
(populated at INSERT time by `SealSummaryProjection`). Matches the
shape of every other federation list_* slice
(`list_credentials.credential_id`, `list_permits.permit_id`).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per [[project_authz_future]] watch items).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.federation.errors import UnauthorizedError
from cora.federation.features.list_seals.query import ListSeals
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class SealSummaryItem:
    """One row from the Seal singleton-per-facility projection."""

    facility_id: str
    seal_stream_id: UUID
    online_credential_id: UUID
    offline_credential_id: UUID
    current_head_hash: str | None
    current_sequence_number: int
    initialized_by_actor_id: UUID
    last_signed_by_actor_id: UUID | None
    status: str
    initialized_at: datetime
    last_signed_at: datetime | None


@dataclass(frozen=True)
class SealListPage:
    """A page of Seal summaries plus the cursor for the next page."""

    items: list[SealSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_seals handler implements."""

    async def __call__(
        self,
        query: ListSeals,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> SealListPage: ...


_SELECT_COLUMNS = (
    "facility_id, seal_stream_id, "
    "online_credential_id, offline_credential_id, "
    "current_head_hash, current_sequence_number, "
    "initialized_by_actor_id, last_signed_by_actor_id, "
    "status, initialized_at, last_signed_at"
)


def _row_to_item(row: Any) -> SealSummaryItem:
    return SealSummaryItem(
        facility_id=str(row["facility_id"]),
        seal_stream_id=row["seal_stream_id"],
        online_credential_id=row["online_credential_id"],
        offline_credential_id=row["offline_credential_id"],
        current_head_hash=(
            str(row["current_head_hash"]) if row["current_head_hash"] is not None else None
        ),
        current_sequence_number=int(row["current_sequence_number"]),
        initialized_by_actor_id=row["initialized_by_actor_id"],
        last_signed_by_actor_id=row["last_signed_by_actor_id"],
        status=str(row["status"]),
        initialized_at=row["initialized_at"],
        last_signed_at=row["last_signed_at"],
    )


def _log_fields(query: ListSeals) -> dict[str, Any]:
    return {"status": query.status}


def bind(deps: Kernel) -> Handler:
    """Build a list_seals handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListSeals",
        log_prefix="list_seals",
        unauthorized_error=UnauthorizedError,
        table="proj_federation_seal_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="initialized_at",
        id_column="seal_stream_id",
        filters=[ScalarFilter(attr="status")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.initialized_at,
        item_cursor_id=lambda item: item.seal_stream_id,
        page_from=lambda items, next_cursor: SealListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "SealListPage",
    "SealSummaryItem",
    "bind",
]
