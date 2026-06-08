# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Application handler for the `get_permit` query slice.

Single-row read from `proj_federation_permit_summary`:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. SELECT * FROM proj_federation_permit_summary WHERE permit_id = $1
    3. row -> PermitView (flat); raise PermitNotFoundError if missing

The projection columns carry the polymorphic terms split across
per-direction columns (NULL on the opposite arc), so the view exposes
both arcs as optional fields and the route DTO reconstructs the
tagged-union wire envelope discriminated by `terms_kind`.

Per Path C the lifecycle bookkeeping timestamps (`defined_at`,
`activated_at`, `suspended_at`, `resumed_at`, `revoked_at`) live on
the projection and ride on the view directly.

Query handlers do NOT emit `causation_id` log fields; queries have no
causation chain. The 404 mapping is handled at the route level via the
BC's `PermitNotFoundError` exception handler registered in
`federation.routes`.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.federation.aggregates.permit import PermitNotFoundError
from cora.federation.errors import UnauthorizedError
from cora.federation.features.get_permit.query import GetPermit
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetPermit"

_log = get_logger(__name__)


_SELECT_PERMIT_SQL = """
SELECT permit_id, peer_facility_id, direction,
       allowed_credential_ids, allowed_payload_types, allowed_artifact_kinds,
       abi_tier_floor, expires_at, defined_by, status, terms_kind,
       read_scope, onward_action_scope, scopes,
       accepted_canonicalization_versions, required_receipt_kinds,
       publisher_grant_correlation_handle, inbound_allowed_artifact_kinds,
       defined_at, activated_at, suspended_at, resumed_at, revoked_at
FROM proj_federation_permit_summary
WHERE permit_id = $1
"""


@dataclass(frozen=True, slots=True)
class PermitView:
    """Flat read-side bundle keyed off `proj_federation_permit_summary`.

    Per-arc fields are populated only for their owning direction (the
    opposite arc stays `None`); `terms_kind` mirrors `direction` and
    is the wire discriminator. Lifecycle timestamps follow Path C and
    are projection-sourced.
    """

    permit_id: UUID
    peer_facility_code: str
    direction: str
    allowed_credential_ids: list[UUID]
    allowed_payload_types: list[str]
    allowed_artifact_kinds: list[str]
    abi_tier_floor: str
    expires_at: datetime
    defined_by: UUID
    status: str
    terms_kind: str
    read_scope: str | None
    onward_action_scope: str | None
    scopes: list[dict[str, Any]] | None
    accepted_canonicalization_versions: list[str] | None
    required_receipt_kinds: list[str] | None
    publisher_grant_correlation_handle: str | None
    inbound_allowed_artifact_kinds: list[str] | None
    defined_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    resumed_at: datetime | None
    revoked_at: datetime | None


def _jsonb_to_list(value: Any) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return list(value)  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(value, str):
        decoded = json.loads(value)
        if not isinstance(decoded, list):
            msg = f"Expected jsonb array, got {type(decoded).__name__}"
            raise ValueError(msg)
        return list(decoded)  # pyright: ignore[reportUnknownArgumentType]
    msg = f"Unsupported jsonb value type: {type(value).__name__}"
    raise ValueError(msg)


def _row_to_view(row: Any) -> PermitView:
    raw_credentials = _jsonb_to_list(row["allowed_credential_ids"]) or []
    return PermitView(
        permit_id=row["permit_id"],
        peer_facility_code=row["peer_facility_id"],
        direction=row["direction"],
        allowed_credential_ids=[UUID(c) if isinstance(c, str) else c for c in raw_credentials],
        allowed_payload_types=_jsonb_to_list(row["allowed_payload_types"]) or [],
        allowed_artifact_kinds=_jsonb_to_list(row["allowed_artifact_kinds"]) or [],
        abi_tier_floor=row["abi_tier_floor"],
        expires_at=row["expires_at"],
        defined_by=row["defined_by"],
        status=row["status"],
        terms_kind=row["terms_kind"],
        read_scope=row["read_scope"],
        onward_action_scope=row["onward_action_scope"],
        scopes=_jsonb_to_list(row["scopes"]),
        accepted_canonicalization_versions=_jsonb_to_list(
            row["accepted_canonicalization_versions"]
        ),
        required_receipt_kinds=_jsonb_to_list(row["required_receipt_kinds"]),
        publisher_grant_correlation_handle=row["publisher_grant_correlation_handle"],
        inbound_allowed_artifact_kinds=_jsonb_to_list(row["inbound_allowed_artifact_kinds"]),
        defined_at=row["defined_at"],
        activated_at=row["activated_at"],
        suspended_at=row["suspended_at"],
        resumed_at=row["resumed_at"],
        revoked_at=row["revoked_at"],
    )


class Handler(Protocol):
    """Callable interface every get_permit handler implements."""

    async def __call__(
        self,
        query: GetPermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PermitView: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_permit handler closed over the shared deps."""

    async def handler(
        query: GetPermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PermitView:
        _log.info(
            "get_permit.start",
            query_name=_QUERY_NAME,
            permit_id=str(query.permit_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_permit.denied",
                query_name=_QUERY_NAME,
                permit_id=str(query.permit_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        if deps.pool is None:
            _log.info(
                "get_permit.no_pool",
                query_name=_QUERY_NAME,
                permit_id=str(query.permit_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            raise PermitNotFoundError(query.permit_id)

        async with deps.pool.acquire() as conn:
            row = await conn.fetchrow(_SELECT_PERMIT_SQL, query.permit_id)

        if row is None:
            _log.info(
                "get_permit.not_found",
                query_name=_QUERY_NAME,
                permit_id=str(query.permit_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            raise PermitNotFoundError(query.permit_id)

        view = _row_to_view(row)
        _log.info(
            "get_permit.success",
            query_name=_QUERY_NAME,
            permit_id=str(query.permit_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            direction=view.direction,
            status=view.status,
        )
        return view

    return handler
