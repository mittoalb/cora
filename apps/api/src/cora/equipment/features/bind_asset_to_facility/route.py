"""HTTP route for the `bind_asset_to_facility` slice.

POST /assets/{asset_id}/bind-to-facility: bind an existing Asset to
its owning Federation Facility by recording the facility_code
cross-BC reference on the Asset stream. 204 No Content on success.

Set-once per [[project-slice8-design]] L2: the slice rejects with
HTTP 409 if the target Asset already carries a facility_code
(whether set at register_asset time or at a prior
bind_asset_to_facility call). Rebind path is decommission +
re-register.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.bind_asset_to_facility.command import BindAssetToFacility
from cora.equipment.features.bind_asset_to_facility.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


class BindAssetToFacilityRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/bind-to-facility`."""

    facility_code: str = Field(
        ...,
        min_length=1,
        max_length=FACILITY_CODE_MAX_LENGTH,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=(
            "Cross-deployment Facility slug (for example 'aps', 'maxiv'). "
            "Lowercase ASCII alphanumeric plus dash, 1-32 chars. The "
            "handler resolves the slug via the Federation BC's "
            "FacilityLookup port; unknown codes raise HTTP 404. "
            "Decommissioned-Facility binding is allowed."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.bind_asset_to_facility
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/bind-to-facility",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Either the Asset does not exist (AssetNotFoundError) OR "
                "facility_code does not resolve to a Facility row in the "
                "Federation projection (AssetFacilityNotFoundError). "
                "Operator remedies: register the missing parent first "
                "(`POST /federation/facilities`), or correct the slug."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset is already bound to a Facility "
                "(AssetFacilityCodeAlreadyAssignedError; set-once per "
                "Slice 8 Lock L2; rebind requires decommission + "
                "re-register)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "malformed facility_code, regex violation)."
            ),
        },
    },
    summary="Bind an existing Asset to its owning Federation Facility (set-once)",
)
async def post_assets_bind_to_facility(
    asset_id: Annotated[UUID, Path(description="Target Asset's id.")],
    body: BindAssetToFacilityRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        BindAssetToFacility(asset_id=asset_id, facility_code=body.facility_code),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
