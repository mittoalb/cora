"""HTTP route for the `add_asset_capability` slice.

Action endpoint at `POST /assets/{asset_id}/add_capability`. Body
carries `capability_id`. 204 No Content on success. Same action-
endpoint pattern as the other Asset transition slices.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.add_asset_capability.command import AddAssetCapability
from cora.equipment.features.add_asset_capability.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class AddAssetCapabilityRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/add_capability`.

    Eventual-consistency: `capability_id` is NOT verified against the
    Capability stream at decide time; mismatch surfaces at Plan
    binding (6e).
    """

    capability_id: UUID = Field(
        ...,
        description=(
            "Capability id to add to the asset's capability set. "
            "Eventual-consistency: existence is NOT verified."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_asset_capability
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/add_capability",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset cannot accept the capability under current "
                "conditions (asset is Decommissioned, OR the capability "
                "is already in the asset's capability set), OR a "
                "concurrent write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Add a Capability to an existing asset's capability set",
)
async def post_assets_add_capability(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: AddAssetCapabilityRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        AddAssetCapability(asset_id=asset_id, capability_id=body.capability_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
