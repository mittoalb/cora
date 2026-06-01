"""Application handler for the `list_permits` query slice.

Reads `proj_federation_permit_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Three
optional scalar filters: `direction` / `status` / `peer_facility_id`.
Cursor pagination keyed on `(defined_at, permit_id)`.

List output deliberately OMITS the per-arc terms detail
(read_scope / onward_action_scope / scopes / accepted_canonicalization_versions /
required_receipt_kinds / publisher_grant_correlation_handle /
inbound_allowed_artifact_kinds) to keep the list payload thin;
surfaces only the discriminator `terms_kind` + the cross-direction
shared scope sets. Fetch `get_permit` for the full polymorphic terms
VO.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
per [[project_authz_future]].
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.federation.errors import UnauthorizedError
from cora.federation.features.list_permits.query import ListPermits
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class PermitSummaryItem:
    """One row from the permit projection (shared cross-direction fields only)."""

    permit_id: UUID
    peer_facility_id: str
    direction: str
    allowed_credential_ids: list[Any]
    allowed_payload_types: list[Any]
    allowed_artifact_kinds: list[Any]
    abi_tier_floor: str
    expires_at: datetime
    defined_by_actor_id: UUID
    status: str
    terms_kind: str
    defined_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    resumed_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True)
class PermitListPage:
    """A page of permit summaries plus the cursor for the next page."""

    items: list[PermitSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_permits handler implements."""

    async def __call__(
        self,
        query: ListPermits,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PermitListPage: ...


_SELECT_COLUMNS = (
    "permit_id, peer_facility_id, direction, "
    "allowed_credential_ids, allowed_payload_types, allowed_artifact_kinds, "
    "abi_tier_floor, expires_at, defined_by_actor_id, status, terms_kind, "
    "defined_at, activated_at, suspended_at, resumed_at, revoked_at"
)


def _row_to_item(row: Any) -> PermitSummaryItem:
    return PermitSummaryItem(
        permit_id=row["permit_id"],
        peer_facility_id=str(row["peer_facility_id"]),
        direction=str(row["direction"]),
        allowed_credential_ids=list(row["allowed_credential_ids"]),
        allowed_payload_types=list(row["allowed_payload_types"]),
        allowed_artifact_kinds=list(row["allowed_artifact_kinds"]),
        abi_tier_floor=str(row["abi_tier_floor"]),
        expires_at=row["expires_at"],
        defined_by_actor_id=row["defined_by_actor_id"],
        status=str(row["status"]),
        terms_kind=str(row["terms_kind"]),
        defined_at=row["defined_at"],
        activated_at=row["activated_at"],
        suspended_at=row["suspended_at"],
        resumed_at=row["resumed_at"],
        revoked_at=row["revoked_at"],
    )


def _log_fields(query: ListPermits) -> dict[str, Any]:
    return {
        "direction": query.direction,
        "status": query.status,
        "peer_facility_id": query.peer_facility_id,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_permits handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListPermits",
        log_prefix="list_permits",
        unauthorized_error=UnauthorizedError,
        table="proj_federation_permit_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="defined_at",
        id_column="permit_id",
        filters=[
            ScalarFilter(attr="direction"),
            ScalarFilter(attr="status"),
            ScalarFilter(attr="peer_facility_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.defined_at,
        item_cursor_id=lambda item: item.permit_id,
        page_from=lambda items, next_cursor: PermitListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "PermitListPage",
    "PermitSummaryItem",
    "bind",
]
