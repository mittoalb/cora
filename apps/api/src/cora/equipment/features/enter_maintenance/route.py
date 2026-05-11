"""HTTP route for the `enter_maintenance` slice.

Action endpoint at `POST /assets/{asset_id}/enter_maintenance`. Same
action-endpoint pattern as the other Asset transition slices. 204 No
Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment.features.enter_maintenance.command import EnterMaintenance
from cora.equipment.features.enter_maintenance.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.enter_maintenance
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/enter_maintenance",
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
                "Asset is not in `Active` lifecycle (enter_maintenance "
                "requires Active), OR a concurrent write to the same "
                "asset stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Take an existing (Active) asset out of service for maintenance",
)
async def post_assets_enter_maintenance(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        EnterMaintenance(asset_id=asset_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
