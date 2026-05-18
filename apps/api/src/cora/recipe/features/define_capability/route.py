"""HTTP route for the `define_capability` slice.

Pydantic request/response schemas + APIRouter for `POST /capabilities`.
The slice's BC-level wiring (`cora.recipe.routes.register_recipe_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_DESCRIPTION_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.define_capability.command import DefineCapability
from cora.recipe.features.define_capability.handler import IdempotentHandler


class DefineCapabilityRequest(BaseModel):
    """Body for `POST /capabilities`."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=CAPABILITY_CODE_MAX_LENGTH,
        description=(
            "Namespaced machine-readable code under `cora.capability.*` "
            "(closed core) or `cora.capability.<facility>.*` (namespaced "
            "facility extension). Immutable across versions."
        ),
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=CAPABILITY_NAME_MAX_LENGTH,
        description="Display name for the new Capability.",
    )
    required_affordances: list[Affordance] = Field(
        ...,
        description=(
            "Family.affordance contract any implementer must satisfy. "
            "Required at definition time; supply `[]` explicitly when "
            "the Capability is parameter-driven without an affordance "
            "requirement. Deduplicated server-side."
        ),
    )
    executor_shapes: list[ExecutorShape] = Field(
        ...,
        description=(
            "Closed-enum set of executor kinds that may implement this "
            "Capability ({Method, Procedure} at v1). Required non-empty "
            "(a Capability with no executor kinds has no operational "
            "meaning). Deduplicated server-side."
        ),
    )
    description: str | None = Field(
        default=None,
        max_length=CAPABILITY_DESCRIPTION_MAX_LENGTH,
        description="Optional human description (0-2000 chars).",
    )
    parameter_schema: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional declarative JSON Schema for the parameter contract. "
            "Method.parameters_schema (6g) must validate as a subset of "
            "this contract at define_method time per the cross-BC STRICT "
            "anchor. Constrained subset: $schema/type/required/properties/"
            "enum/minimum/maximum/pattern allowed; $ref/oneOf/anyOf/allOf/"
            "not forbidden."
        ),
    )


class DefineCapabilityResponse(BaseModel):
    """Response body for `POST /capabilities`."""

    capability_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.recipe.define_capability
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/capabilities",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineCapabilityResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only name, "
                "bad code namespace, empty executor_shapes, malformed "
                "parameter_schema)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new universal Capability template at the operations layer",
)
async def post_capabilities(
    body: DefineCapabilityRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the Capability."
            ),
        ),
    ] = None,
) -> DefineCapabilityResponse:
    capability_id = await handler(
        DefineCapability(
            code=body.code,
            name=body.name,
            description=body.description,
            required_affordances=frozenset(body.required_affordances),
            executor_shapes=frozenset(body.executor_shapes),
            parameter_schema=body.parameter_schema,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return DefineCapabilityResponse(capability_id=capability_id)
