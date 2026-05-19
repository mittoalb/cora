"""HTTP route for the `get_surface` query slice."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.trust.aggregates.surface import SURFACE_NAME_MAX_LENGTH, SurfaceKind, SurfaceStatus
from cora.trust.features.get_surface.handler import Handler
from cora.trust.features.get_surface.query import GetSurface


class SurfaceResponse(BaseModel):
    """Read-side DTO at the API boundary."""

    id: UUID
    name: str = Field(..., max_length=SURFACE_NAME_MAX_LENGTH)
    kind: SurfaceKind
    status: SurfaceStatus
    defined_at: datetime
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.get_surface
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/surfaces/{surface_id}",
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
    surface_id: Annotated[UUID, Path(description="Target surface's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> SurfaceResponse:
    surface = await handler(
        GetSurface(surface_id=surface_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if surface is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Surface {surface_id} not found",
        )
    return SurfaceResponse(
        id=surface.id,
        name=surface.name.value,
        kind=surface.kind,
        status=surface.status,
        defined_at=surface.defined_at,
        versioned_at=surface.versioned_at,
        deprecated_at=surface.deprecated_at,
    )
