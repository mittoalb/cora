"""HTTP route for the `remove_asset_family` slice.

Action endpoint at `POST /assets/{asset_id}/remove-family`. Body
carries `family_id`. 204 No Content on success.

POST (not DELETE) for symmetry with `add-family` and the rest of
Equipment's action-endpoint convention. The semantics aren't really
"REST collection management" — they're "operator decommissions a
family on this asset," which is a state-change verb.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.remove_asset_family.command import RemoveAssetFamily
from cora.equipment.features.remove_asset_family.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RemoveAssetFamilyRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/remove-family`."""

    family_id: UUID = Field(
        ...,
        description="Family id to remove from the asset's family set.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.remove_asset_family
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/remove-family",
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
                "Asset cannot remove the family under current "
                "conditions (asset is Decommissioned, OR the family "
                "is not in the asset's family set), OR a concurrent "
                "write to the same asset stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Remove a Family from an existing asset's family set",
)
async def post_assets_remove_family(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: RemoveAssetFamilyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveAssetFamily(asset_id=asset_id, family_id=body.family_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
