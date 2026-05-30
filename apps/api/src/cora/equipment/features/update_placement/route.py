"""HTTP route for the `update_placement` slice."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment._placement_body import PlacementBody
from cora.equipment.features.update_placement.command import UpdatePlacement
from cora.equipment.features.update_placement.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class UpdatePlacementRequest(BaseModel):
    new_placement: PlacementBody = Field(..., description="The new placement.")
    survey: dict[str, Any] | None = Field(
        None,
        description=("Optional re-survey provenance carried onto the event payload."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.update_placement
    return handler


router = APIRouter(tags=["equipment"])


@router.patch(
    "/mounts/{mount_id}/placement",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Update a mount's placement relative to its parent frame",
)
async def patch_mount_placement(
    mount_id: UUID,
    body: UpdatePlacementRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdatePlacement(
            mount_id=mount_id,
            new_placement=body.new_placement.to_domain(),
            survey=body.survey,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
