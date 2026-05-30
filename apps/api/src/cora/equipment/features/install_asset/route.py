"""HTTP route for the `install_asset` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.install_asset.command import InstallAsset
from cora.equipment.features.install_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class InstallAssetRequest(BaseModel):
    asset_id: UUID = Field(..., description="The Asset specimen to install.")


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.install_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.put(
    "/mounts/{mount_id}/installed-asset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Mount or Asset does not exist.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Mount cannot accept install: already Decommissioned "
                "OR slot is already occupied by another Asset (uninstall "
                "first; no implicit eviction)."
            ),
        },
    },
    summary="Install an Asset specimen into a mount slot",
)
async def put_mount_installed_asset(
    mount_id: UUID,
    body: InstallAssetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        InstallAsset(mount_id=mount_id, asset_id=body.asset_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
