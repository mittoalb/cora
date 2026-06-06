"""HTTP route for the `unbind_plan_role` slice.

Action endpoint at `POST /plans/{plan_id}/unbind-role`. Body carries
only the `role_name`. 204 No Content on success.
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
from cora.recipe.aggregates.method import ROLE_NAME_MAX_LENGTH, RoleName
from cora.recipe.features.unbind_plan_role.command import UnbindPlanRole
from cora.recipe.features.unbind_plan_role.handler import Handler


class UnbindPlanRoleRequest(BaseModel):
    """Body for `POST /plans/{plan_id}/unbind-role`."""

    role_name: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_NAME_MAX_LENGTH,
        description=(
            "The role_name whose binding to remove. Strict-not-"
            "idempotent: an unknown role_name returns 404."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.unbind_plan_role
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/{plan_id}/unbind-role",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "role_name VO validation failed (empty / whitespace-only or too-long string)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No plan exists with the given id, OR no binding with "
                "the given role_name is present on the plan."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Plan cannot unbind the role under current conditions: "
                "Plan is Versioned/Deprecated, OR a concurrent write "
                "to the same Plan stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Remove a role binding from an existing Plan",
)
async def post_plans_unbind_role(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    body: UnbindPlanRoleRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UnbindPlanRole(
            plan_id=plan_id,
            role_name=RoleName(body.role_name),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
