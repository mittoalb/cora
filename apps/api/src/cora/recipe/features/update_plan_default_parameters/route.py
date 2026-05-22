"""HTTP route for the `update_plan_default_parameters` slice.

Action endpoint at
`PATCH /plans/{plan_id}/default-parameters`. Body carries
`default_parameters_patch` — a partial dict applied with RFC 7396
JSON Merge Patch semantics. 204 No Content on success.

Uses HTTP PATCH (precedent: 5g-c update_asset_settings) because
PATCH is the right verb for partial-update semantics on a sub-
resource. The body shape is `{default_parameters_patch: {...}}`
rather than the patch dict directly so the request envelope can
grow additional fields in a future additive revision without
breaking clients.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.features.update_plan_default_parameters.command import (
    UpdatePlanDefaultParameters,
)
from cora.recipe.features.update_plan_default_parameters.handler import Handler


class UpdatePlanDefaultParametersRequest(BaseModel):
    """Body for `PATCH /plans/{plan_id}/default-parameters`.

    `default_parameters_patch` is a dict applied with RFC 7396
    (JSON Merge Patch) semantics:
      - keys with non-null values are set / replaced
      - keys with null are deleted from default_parameters
      - absent keys are preserved

    The decider validates the post-merge result against the owning
    Method's `parameters_schema` (loaded by the handler). Strict when
    the Method declares no schema: non-empty defaults are rejected
    (operators wanting parameter-less Methods declare
    `parameters_schema={}` explicitly). Validation failure surfaces
    as HTTP 400.
    """

    default_parameters_patch: dict[str, Any] = Field(
        ...,
        description=(
            "Partial default_parameters dict. RFC 7396 merge "
            "semantics: non-null values set/replace; null values "
            "delete; absent keys are preserved."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.update_plan_default_parameters
    return handler


router = APIRouter(tags=["recipe"])


@router.patch(
    "/plans/{plan_id}/default-parameters",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "The proposed default_parameters (after merge) "
                "failed validation against the owning Method's "
                "parameters_schema."
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
                "A concurrent write to the same plan stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing "
                "default_parameters_patch field, malformed UUID in path, etc.)."
            ),
        },
    },
    summary="Update an existing plan's default_parameters dict (RFC 7396 merge semantics)",
)
async def patch_plan_default_parameters(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    body: UpdatePlanDefaultParametersRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdatePlanDefaultParameters(
            plan_id=plan_id, default_parameters_patch=body.default_parameters_patch
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
