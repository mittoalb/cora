"""Application handler for the `list_credentials` query slice.

Reads `proj_federation_credential_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Three
optional scalar filters: `facility_id`, `purpose`, `status`. Cursor
pagination keyed on `(registered_at, credential_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per `memory/project_authz_future.md`).

Vault hygiene: opaque secret-material refs (`secret_ref`,
`public_material_ref`, `rotation_pending_*_ref`) are intentionally
NOT in `_SELECT_COLUMNS`; surface only the identifying / lifecycle
columns here. `get_credential` is the path for ref inspection by
callers entitled to handle the opaque pointer.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.federation.errors import UnauthorizedError
from cora.federation.features.list_credentials.query import ListCredentials
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import (
    ScalarFilter,
    make_list_query_handler,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class CredentialSummaryItem:
    """One row from the credential projection (opaque refs omitted)."""

    credential_id: UUID
    facility_id: str
    audience: str
    purpose: str
    expires_at: datetime | None
    status: str
    registered_at: datetime
    rotation_started_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True)
class CredentialListPage:
    """A page of credential summaries plus the cursor for the next page."""

    items: list[CredentialSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_credentials handler implements."""

    async def __call__(
        self,
        query: ListCredentials,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CredentialListPage: ...


_SELECT_COLUMNS = (
    "credential_id, facility_id, audience, purpose, expires_at, status, "
    "registered_at, rotation_started_at, revoked_at"
)


def _row_to_item(row: Any) -> CredentialSummaryItem:
    return CredentialSummaryItem(
        credential_id=row["credential_id"],
        facility_id=str(row["facility_id"]),
        audience=str(row["audience"]),
        purpose=str(row["purpose"]),
        expires_at=row["expires_at"],
        status=str(row["status"]),
        registered_at=row["registered_at"],
        rotation_started_at=row["rotation_started_at"],
        revoked_at=row["revoked_at"],
    )


def _log_fields(query: ListCredentials) -> dict[str, Any]:
    return {
        "facility_id": query.facility_id,
        "purpose": query.purpose,
        "status": query.status,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_credentials handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListCredentials",
        log_prefix="list_credentials",
        unauthorized_error=UnauthorizedError,
        table="proj_federation_credential_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="credential_id",
        filters=[
            ScalarFilter(attr="facility_id"),
            ScalarFilter(attr="purpose"),
            ScalarFilter(attr="status"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.credential_id,
        page_from=lambda items, next_cursor: CredentialListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "CredentialListPage",
    "CredentialSummaryItem",
    "Handler",
    "bind",
]
