"""HTTP route for the `list_credentials` query slice.

`GET /federation/credentials` accepts these optional query params:
`cursor`, `limit`, `facility_id`, `purpose`, `status`. Returns
`{"items": [...], "next_cursor": "..." | null}`.

Opaque secret-material refs (`secret_ref`, `public_material_ref`,
`rotation_pending_*_ref`) are NEVER surfaced by this endpoint per
vault hygiene; fetch via `get_credential` when needed.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel

from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.features.list_credentials.handler import Handler
from cora.federation.features.list_credentials.query import (
    CredentialPurposeFilter,
    CredentialStatusFilter,
    ListCredentials,
)
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class CredentialSummaryDTO(BaseModel):
    """One credential in a paginated list. Opaque refs intentionally omitted."""

    credential_id: UUID
    facility_id: str
    audience: str
    purpose: CredentialPurpose
    expires_at: datetime | None = None
    status: CredentialStatus
    registered_at: datetime
    rotation_started_at: datetime | None = None
    revoked_at: datetime | None = None


class CredentialListResponse(BaseModel):
    """Page of credentials plus opaque next-page cursor."""

    items: list[CredentialSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.list_credentials
    return handler


router = APIRouter(tags=["federation"])


@router.get(
    "/federation/credentials",
    status_code=status.HTTP_200_OK,
    response_model=CredentialListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Query parameters failed validation OR `cursor` was malformed.",
        },
    },
    summary=(
        "List credentials with cursor pagination + facility_id / purpose / "
        "status filters. Opaque secret refs are NOT surfaced; fetch "
        "get_credential for those."
    ),
)
async def list_credentials(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    facility_id: Annotated[
        str | None,
        Query(description="Optional facility filter; matches the credential's facility_id."),
    ] = None,
    purpose: Annotated[
        CredentialPurposeFilter | None,
        Query(description="Optional purpose filter (one of the 6 CredentialPurpose values)."),
    ] = None,
    status_filter: Annotated[
        CredentialStatusFilter | None,
        Query(
            alias="status",
            description="Optional status filter (one of Active / Rotating / Revoked).",
        ),
    ] = None,
) -> CredentialListResponse:
    page = await handler(
        ListCredentials(
            cursor=cursor,
            limit=limit,
            facility_id=facility_id,
            purpose=purpose,
            status=status_filter,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return CredentialListResponse(
        items=[
            CredentialSummaryDTO(
                credential_id=item.credential_id,
                facility_id=item.facility_id,
                audience=item.audience,
                purpose=CredentialPurpose(item.purpose),
                expires_at=item.expires_at,
                status=CredentialStatus(item.status),
                registered_at=item.registered_at,
                rotation_started_at=item.rotation_started_at,
                revoked_at=item.revoked_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


__all__ = ["CredentialListResponse", "CredentialSummaryDTO", "router"]
