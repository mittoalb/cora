"""HTTP route for the `add_facility_trust_anchor_credential` slice.

Action endpoint at
`POST /federation/facilities/{facility_id}/add-trust-anchor-credential`.
Body carries `credential_id`. Returns 204 on success.

Mirrors the `decommission_facility` route shape: lifecycle / trust-
anchor mutation sits under the resource via verb, not as PUT/PATCH on
a sub-collection, because the audit gesture is what matters
(operationally distinct from "edit a field"). The credential_id flows
to the FacilityTrustAnchorCredentialAdded event payload.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.features.add_facility_trust_anchor_credential.command import (
    AddFacilityTrustAnchorCredential,
)
from cora.federation.features.add_facility_trust_anchor_credential.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddFacilityTrustAnchorCredentialBody(BaseModel):
    """Body for `POST /federation/facilities/{facility_id}/add-trust-anchor-credential`."""

    credential_id: UUID = Field(
        ...,
        description=(
            "Credential id to add to the Facility's trust-anchor set. Once "
            "added, the Slice 6 Sub-Slice C Seal decider rewrite will accept "
            "this credential as a valid online or offline signing key for "
            "Seal initialization and rotation on this Facility."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.add_facility_trust_anchor_credential
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/facilities/{facility_id}/add-trust-anchor-credential",
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
                "Either the credential id is already a trust anchor on this "
                "facility (strict-not-idempotent), OR the facility is "
                "Decommissioned (no trust-anchor mutations on retired "
                "facilities), OR the facility is kind=Area (Area facilities "
                "inherit the parent Site's trust posture; trust anchors bind "
                "to Site-tier facilities only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Request body failed schema validation (missing credential_id, malformed UUID)."
            ),
        },
    },
    summary="Bind a Credential as a Facility trust anchor (strict-not-idempotent)",
)
async def post_federation_facilities_add_trust_anchor_credential(
    facility_id: Annotated[UUID, Path(description="Target facility's id.")],
    body: AddFacilityTrustAnchorCredentialBody,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddFacilityTrustAnchorCredential(
            facility_id=FacilityId(facility_id),
            credential_id=CredentialId(body.credential_id),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
