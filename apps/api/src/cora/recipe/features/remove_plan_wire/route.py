"""HTTP route for the `remove_plan_wire` slice (Phase 6h).

Action endpoint at `POST /plans/{plan_id}/remove_wire`. Body
carries the four port-reference fields (the Wire's identity).
204 No Content on success. Same action-endpoint pattern as
`remove_asset_port` (5h).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.plan import WIRE_PORT_NAME_MAX_LENGTH
from cora.recipe.features.remove_plan_wire.command import RemovePlanWire
from cora.recipe.features.remove_plan_wire.handler import Handler


class RemovePlanWireRequest(BaseModel):
    """Body for `POST /plans/{plan_id}/remove_wire`.

    All four fields are required (the 4-tuple identifies the Wire to
    remove). Pydantic enforces non-empty port names at the boundary.
    Removal is strict-not-idempotent: the Wire MUST currently exist
    in the Plan's wire set.
    """

    source_asset_id: UUID = Field(..., description="The source-side Asset of the Wire to remove.")
    source_port_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
        description="Source port name of the Wire to remove.",
    )
    target_asset_id: UUID = Field(..., description="The target-side Asset of the Wire to remove.")
    target_port_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
        description="Target port name of the Wire to remove.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.remove_plan_wire
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/{plan_id}/remove_wire",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "A port name is empty / whitespace-only / exceeds the "
                "configured max length after trimming "
                "(InvalidWireError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Either no plan exists with the given id "
                "(PlanNotFoundError), OR the Wire is not in the Plan's "
                "wire set (PlanWireNotFoundError; strict-not-idempotent)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Concurrent write to the same plan stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID, etc.)."
            ),
        },
    },
    summary="Remove a typed port-to-port Wire from an existing Plan's wire set",
)
async def post_plans_remove_wire(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    body: RemovePlanWireRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemovePlanWire(
            plan_id=plan_id,
            source_asset_id=body.source_asset_id,
            source_port_name=body.source_port_name,
            target_asset_id=body.target_asset_id,
            target_port_name=body.target_port_name,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
