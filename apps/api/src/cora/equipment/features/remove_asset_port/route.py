"""HTTP route for the `remove_asset_port` slice (Phase 5h).

Action endpoint at `POST /assets/{asset_id}/remove_port`. Body
carries `port_name`. 204 No Content on success. Mirror of
`add_asset_port` route.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import PORT_NAME_MAX_LENGTH
from cora.equipment.features.remove_asset_port.command import RemoveAssetPort
from cora.equipment.features.remove_asset_port.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class RemoveAssetPortRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/remove_port`."""

    port_name: str = Field(
        ...,
        min_length=1,
        max_length=PORT_NAME_MAX_LENGTH,
        description="Name of the port to remove.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.remove_asset_port
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/remove_port",
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
                "Asset cannot remove the port under current conditions "
                "(asset is Decommissioned, OR no port with this name "
                "exists on the asset), OR a concurrent write to the "
                "same asset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Remove a typed port from an existing Asset's port set",
)
async def post_assets_remove_port(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: RemoveAssetPortRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        RemoveAssetPort(asset_id=asset_id, port_name=body.port_name),
        principal_id=principal_id,
        correlation_id=cid,
    )
