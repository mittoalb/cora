"""HTTP route for the `version_capability` slice."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.capability import (
    CAPABILITY_DESCRIPTION_MAX_LENGTH,
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.version_capability.command import VersionCapability
from cora.recipe.features.version_capability.handler import Handler


class VersionCapabilityRequest(BaseModel):
    """Body for `POST /capabilities/{capability_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=CAPABILITY_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific."
        ),
    )
    required_affordances: list[Affordance] = Field(
        ...,
        description=(
            "Replacement required_affordances for the new version. A new "
            "version IS a new declaration; the supplied set REPLACES the "
            "prior set wholesale. Supply `[]` to clear all required "
            "affordances."
        ),
    )
    executor_shapes: list[ExecutorShape] = Field(
        ...,
        description=(
            "Replacement executor_shapes for the new version. Required "
            "non-empty (a Capability with no executor kinds has no "
            "operational meaning)."
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
            "Optional declarative JSON Schema (constrained subset) for "
            "the parameter contract. Replaces the prior schema wholesale."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.version_capability
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/capabilities/{capability_id}/version",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": ("Domain invariant violated (whitespace-only version_tag, etc.)."),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Capability exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Capability is currently Deprecated.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Issue a new version label + replacement declarative contract for a Capability",
)
async def post_capabilities_version(
    capability_id: Annotated[UUID, Path(description="Target Capability's id.")],
    body: VersionCapabilityRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        VersionCapability(
            capability_id=capability_id,
            version_tag=body.version_tag,
            description=body.description,
            required_affordances=frozenset(body.required_affordances),
            executor_shapes=frozenset(body.executor_shapes),
            parameter_schema=body.parameter_schema,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
