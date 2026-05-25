"""HTTP route for the `add_plan_wire` slice.

Action endpoint at `POST /plans/{plan_id}/add_wire`. Body carries
the four port-reference fields. 204 No Content on success. Same
action-endpoint pattern as `add_asset_port` (5h) and the rest of
the per-edge mutation slices.
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
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.handler import Handler


class AddPlanWireRequest(BaseModel):
    """Body for `POST /plans/{plan_id}/add_wire`.

    All four fields are required. Pydantic enforces non-empty port
    names at the boundary; the `Wire` VO then trims and re-validates
    length within the decider. Direction + signal_type validation
    happens in the decider against the loaded Asset.ports.
    """

    source_asset_id: UUID = Field(
        ...,
        description="The Asset whose OUTPUT port is the wire's source.",
    )
    source_port_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
        description=(
            "Port name on the source Asset (for example, 'trigger_out', "
            "'data_out'). Must exist on Asset.ports and have "
            "direction=OUTPUT."
        ),
    )
    target_asset_id: UUID = Field(
        ...,
        description="The Asset whose INPUT port is the wire's target.",
    )
    target_port_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
        description=(
            "Port name on the target Asset (for example, 'trigger_in'). "
            "Must exist on Asset.ports, have direction=INPUT, and "
            "match source port's signal_type exactly. At most one "
            "Wire can target a given (target_asset_id, target_port_name) "
            "pair (fan-in forbidden; use a Combiner Family Asset "
            "if you genuinely need multi-source aggregation)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.add_plan_wire
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/{plan_id}/add_wire",
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
            "description": "No plan exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Plan cannot accept the wire under current conditions: "
                "the wire is already in the wire set (PlanWireAlreadyExistsError); "
                "the target port is already wired (PlanWireTargetAlreadyConnectedError, "
                "fan-in forbidden); a referenced Asset is not bound by "
                "this Plan (PlanWireAssetNotBoundError); a referenced "
                "port doesn't exist on its Asset (PlanWirePortNotFoundError); "
                "direction mismatch (PlanWireDirectionMismatchError); "
                "signal_type mismatch (PlanWireSignalTypeMismatchError); "
                "self-loop on the same port (PlanWireSelfLoopError); OR "
                "a concurrent write to the same plan stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID, etc.)."
            ),
        },
    },
    summary="Add a typed port-to-port Wire to an existing Plan's wire set",
)
async def post_plans_add_wire(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    body: AddPlanWireRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddPlanWire(
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
