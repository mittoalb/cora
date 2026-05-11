"""HTTP route for the `version_plan` slice.

Action endpoint at `POST /plans/{plan_id}/version`. Body carries
`version_tag`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.plan import PLAN_VERSION_TAG_MAX_LENGTH
from cora.recipe.features.version_plan.command import VersionPlan
from cora.recipe.features.version_plan.handler import Handler


class VersionPlanRequest(BaseModel):
    """Body for `POST /plans/{plan_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=PLAN_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.version_plan
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/{plan_id}/version",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated: whitespace-only version_tag.",
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
                "Plan is not in `Defined` or `Versioned` status "
                "(version requires one of those), OR a concurrent write "
                "to the same plan stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Issue a new version label for an existing plan",
)
async def post_plans_version(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    body: VersionPlanRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        VersionPlan(plan_id=plan_id, version_tag=body.version_tag),
        principal_id=principal_id,
        correlation_id=cid,
    )
