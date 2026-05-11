"""HTTP route for the `restore_from_maintenance` slice.

Action endpoint at `POST /assets/{asset_id}/restore_from_maintenance`.
Same action-endpoint pattern as the other Asset transition slices.
204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment.features.restore_from_maintenance.command import RestoreFromMaintenance
from cora.equipment.features.restore_from_maintenance.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.restore_from_maintenance
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/restore_from_maintenance",
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
                "Asset is not in `Maintenance` lifecycle "
                "(restore_from_maintenance requires Maintenance), OR a "
                "concurrent write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
    },
    summary="Return an existing (Maintenance) asset to active service",
)
async def post_assets_restore_from_maintenance(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        RestoreFromMaintenance(asset_id=asset_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
