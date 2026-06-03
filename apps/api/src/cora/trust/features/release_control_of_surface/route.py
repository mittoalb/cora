"""HTTP route for the `release_control_of_surface` slice.

Action endpoint at `POST /visits/{visit_id}/surface-control/release`. JSON
body carries `surface_id`. 204 on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.features.release_control_of_surface.command import ReleaseControlOfSurface
from cora.trust.features.release_control_of_surface.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.release_control_of_surface
    return handler


router = APIRouter(tags=["trust"])


class ReleaseControlOfSurfaceBody(BaseModel):
    """Body for POST /visits/{visit_id}/surface-control/release."""

    model_config = ConfigDict(extra="forbid")

    surface_id: UUID = Field(
        description=(
            "Surface that the requesting Visit relinquishes control of. "
            "Must match the Visit's surface_id."
        ),
    )


@router.post(
    "/visits/{visit_id}/surface-control/release",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Visit exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Visit cannot release: requesting Visit is not the current "
                "Surface holder or surface_id does not match."
            ),
        },
    },
    summary="Requesting Visit releases operational control of a Surface",
)
async def post_visits_release_control(
    visit_id: Annotated[UUID, Path(description="Requesting Visit's id.")],
    body: ReleaseControlOfSurfaceBody,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ReleaseControlOfSurface(visit_id=visit_id, surface_id=body.surface_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
