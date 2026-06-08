"""HTTP route for the `remove_facility_trust_anchor_credential` slice.

Action endpoint at
`POST /federation/facilities/{facility_id}/remove-trust-anchor-credential`.
Body carries `credential_id` + optional `reason`. Returns 204 on success.

Mirror of the add route with the verb name flipped + reason field.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.features.remove_facility_trust_anchor_credential.command import (
    RemoveFacilityTrustAnchorCredential,
)
from cora.federation.features.remove_facility_trust_anchor_credential.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RemoveFacilityTrustAnchorCredentialBody(BaseModel):
    """Body for `POST /federation/facilities/{facility_id}/remove-trust-anchor-credential`."""

    credential_id: UUID = Field(
        ...,
        description=(
            "Credential id to remove from the Facility's trust-anchor set. "
            "Strict-not-idempotent: re-removing raises 409."
        ),
    )
    reason: str | None = Field(
        default=None,
        description=(
            "Optional operator-supplied reason for removing the trust anchor "
            "(audit-log breadcrumb; e.g. 'key compromise', 'rotation cleanup'). "
            "Flows onto the FacilityTrustAnchorCredentialRemoved event payload."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.remove_facility_trust_anchor_credential
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/facilities/{facility_id}/remove-trust-anchor-credential",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No facility exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Either the credential id is not a trust anchor on this "
                "facility (strict-not-idempotent; nothing to remove), OR "
                "the facility is Decommissioned (no trust-anchor mutations "
                "on retired facilities)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Request body failed schema validation (missing credential_id, malformed UUID)."
            ),
        },
    },
    summary="Unbind a Credential from a Facility trust anchor (strict-not-idempotent)",
)
async def post_federation_facilities_remove_trust_anchor_credential(
    facility_id: Annotated[UUID, Path(description="Target facility's id.")],
    body: RemoveFacilityTrustAnchorCredentialBody,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveFacilityTrustAnchorCredential(
            facility_id=FacilityId(facility_id),
            credential_id=CredentialId(body.credential_id),
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
