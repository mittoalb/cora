"""HTTP route for the `remove_asset_capability` slice.

Action endpoint at `POST /assets/{asset_id}/remove_capability`. Body
carries `capability_id`. 204 No Content on success.

POST (not DELETE) for symmetry with `add_capability` and the rest of
Equipment's action-endpoint convention. The semantics aren't really
"REST collection management" — they're "operator decommissions a
capability on this asset," which is a state-change verb.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.remove_asset_capability.command import RemoveAssetCapability
from cora.equipment.features.remove_asset_capability.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class RemoveAssetCapabilityRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/remove_capability`."""

    capability_id: UUID = Field(
        ...,
        description="Capability id to remove from the asset's capability set.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.remove_asset_capability
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/remove_capability",
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
                "Asset cannot remove the capability under current "
                "conditions (asset is Decommissioned, OR the capability "
                "is not in the asset's capability set), OR a concurrent "
                "write to the same asset stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Remove a Capability from an existing asset's capability set",
)
async def post_assets_remove_capability(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: RemoveAssetCapabilityRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        RemoveAssetCapability(asset_id=asset_id, capability_id=body.capability_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
