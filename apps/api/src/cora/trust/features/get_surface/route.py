"""HTTP route for the `get_surface` query slice.

Surface is a singleton-ish aggregate (3 hardcoded instances seeded
at boot). Path C dropped the lifecycle timestamps from this
response entirely because they carried no observable read
value (`defined_at` was boot-time on every pod restart;
`versioned_at` / `deprecated_at` were always null in practice). No
projection is built — if a future fourth Surface kind ever becomes
operator-defined, revisit per the Path C pattern in Method/Plan/
Practice/Family/Capability/Agent.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.aggregates.surface import SURFACE_NAME_MAX_LENGTH, SurfaceKind, SurfaceStatus
from cora.trust.features.get_surface.handler import Handler
from cora.trust.features.get_surface.query import GetSurface


class SurfaceResponse(BaseModel):
    """Read-side DTO at the API boundary."""

    id: UUID
    name: str = Field(..., max_length=SURFACE_NAME_MAX_LENGTH)
    kind: SurfaceKind
    status: SurfaceStatus


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.get_surface
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/surfaces/{target_surface_id}",
    status_code=status.HTTP_200_OK,
    response_model=SurfaceResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No surface exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a surface by id",
)
async def get_surfaces(
    target_surface_id: Annotated[UUID, Path(description="Target surface's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> SurfaceResponse:
    surface = await handler(
        GetSurface(surface_id=target_surface_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if surface is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Surface {target_surface_id} not found",
        )
    return SurfaceResponse(
        id=surface.id,
        name=surface.name.value,
        kind=surface.kind,
        status=surface.status,
    )
