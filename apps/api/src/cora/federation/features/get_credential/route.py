"""HTTP route for the `get_credential` query slice.

`GET /federation/credentials/{credential_id}` returns 200 +
`CredentialResponse` on hit, 404 on miss.

Per AH#6 of the locked design, the response surfaces `secret_ref`,
`public_material_ref`, `rotation_pending_secret_ref`, and
`rotation_pending_public_material_ref` as OPAQUE STRINGS only; raw
secret bytes never cross this wire (the aggregate never holds them).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.federation.aggregates.credential import (
    Credential,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.features.get_credential.handler import Handler
from cora.federation.features.get_credential.query import GetCredential
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class CredentialResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Mirrors the Credential aggregate state plus projection-sourced
    lifecycle timestamps. `secret_ref` / `public_material_ref` /
    `rotation_pending_*_ref` are OPAQUE pointers (URI / KMS ARN /
    vault path), never raw secret material.

    `registered_at` and `registered_by` are sourced from aggregate
    state (folded from the genesis envelope per the fold-symmetry
    Path C reversal); `rotation_started_at` is projection-sourced
    and therefore nullable on the wire because the projection may
    transiently lag behind the event store, or the deps may lack a
    configured pool (in-memory test mode). Mirrors the Calibration /
    Method / Plan read DTOs.
    """

    id: UUID
    facility_code: str
    audience: str
    purpose: CredentialPurpose
    secret_ref: str
    public_material_ref: str | None
    expires_at: datetime | None
    registered_by: UUID
    registered_at: datetime
    rotation_pending_secret_ref: str | None
    rotation_pending_public_material_ref: str | None
    status: CredentialStatus
    rotation_started_at: datetime | None = None


def _response_from_view(
    credential: Credential,
    rotation_started_at: datetime | None,
) -> CredentialResponse:
    return CredentialResponse(
        id=credential.id,
        facility_code=credential.facility_code.value,
        audience=credential.audience,
        purpose=credential.purpose,
        secret_ref=credential.secret_ref,
        public_material_ref=credential.public_material_ref,
        expires_at=credential.expires_at,
        registered_by=credential.registered_by,
        registered_at=credential.registered_at,
        rotation_pending_secret_ref=credential.rotation_pending_secret_ref,
        rotation_pending_public_material_ref=credential.rotation_pending_public_material_ref,
        status=credential.status,
        rotation_started_at=rotation_started_at,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.get_credential
    return handler


router = APIRouter(tags=["federation"])


@router.get(
    "/federation/credentials/{credential_id}",
    status_code=status.HTTP_200_OK,
    response_model=CredentialResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No credential exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a federation Credential by id",
)
async def get_federation_credential(
    credential_id: Annotated[UUID, Path(description="Target credential's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> CredentialResponse:
    view = await handler(
        GetCredential(credential_id=credential_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential {credential_id} not found",
        )
    return _response_from_view(
        view.credential,
        view.timestamps.rotation_started_at if view.timestamps is not None else None,
    )
