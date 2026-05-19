"""HTTP route for the `activate_asset` slice.

Action endpoint at `POST /assets/{asset_id}/activate`. Same
action-endpoint pattern as Subject's transition slices. 204 No
Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment.features.activate_asset.command import ActivateAsset
from cora.equipment.features.activate_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.activate_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/activate",
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
                "Asset is not in `Commissioned` lifecycle (activate "
                "requires Commissioned), OR a concurrent write to the "
                "same asset stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Activate an existing (Commissioned) asset, putting it into service",
)
async def post_assets_activate(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ActivateAsset(asset_id=asset_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
