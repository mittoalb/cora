"""HTTP route for the `get_capability` slice.

`GET /capabilities/{capability_id}` returns 200 + CapabilityResponse
on hit, 404 on miss.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.get_capability.handler import Handler
from cora.recipe.features.get_capability.query import GetCapability


class CapabilityResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value (Defined / Versioned / Deprecated). `version` is
    the operator-supplied label of the most recent version_capability
    call (null until first version). `required_affordances` and
    `executor_shapes` serialize as sorted lists for response
    determinism. `replaced_by_capability_id` is null on Defined /
    Versioned / Deprecated-without-replacement; populated when a
    deprecation supplied a successor pointer.
    """

    id: UUID
    code: str = Field(..., max_length=CAPABILITY_CODE_MAX_LENGTH)
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    description: str | None
    required_affordances: list[Affordance]
    executor_shapes: list[ExecutorShape]
    parameter_schema: dict[str, Any] | None
    replaced_by_capability_id: UUID | None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.get_capability
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/capabilities/{capability_id}",
    status_code=status.HTTP_200_OK,
    response_model=CapabilityResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Capability exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a Capability by id",
)
async def get_capabilities(
    capability_id: Annotated[UUID, Path(description="Target Capability's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> CapabilityResponse:
    capability = await handler(
        GetCapability(capability_id=capability_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return CapabilityResponse(
        id=capability.id,
        code=capability.code.value,
        name=capability.name.value,
        status=capability.status.value,
        version=capability.version,
        description=capability.description,
        required_affordances=sorted(capability.required_affordances, key=lambda a: a.value),
        executor_shapes=sorted(capability.executor_shapes, key=lambda s: s.value),
        parameter_schema=capability.parameter_schema,
        replaced_by_capability_id=capability.replaced_by_capability_id,
    )
