"""HTTP route for the `remove_method_required_role` slice.

Action endpoint at `POST /methods/{method_id}/remove-required-role`.
Body carries only the `role_name` (the structural identity within
the Method scope). 204 No Content on success, matching the
remove-style convention in the Recipe BC (see `remove_plan_wire`).
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
from cora.recipe.features.remove_method_required_role.command import (
    RemoveMethodRequiredRole,
)
from cora.recipe.features.remove_method_required_role.handler import Handler


class RemoveMethodRequiredRoleRequest(BaseModel):
    """Body for `POST /methods/{method_id}/remove-required-role`."""

    role_name: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_NAME_MAX_LENGTH,
        description=(
            "The Method-local role label to remove. Strict-not-"
            "idempotent: an unknown role_name returns 404."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.remove_method_required_role
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/methods/{method_id}/remove-required-role",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "role_name VO validation failed: empty / whitespace-"
                "only or too-long string (InvalidRoleNameError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No method exists with the given id, OR no role with "
                "the given role_name is declared on the method "
                "(MethodRoleNameNotFoundError)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Method cannot remove the role under current "
                "conditions: the method is Versioned or Deprecated "
                "(MethodCannotMutateRequiredRolesError), OR a "
                "concurrent write to the same method stream "
                "conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Remove a positional role slot from an existing Method",
)
async def post_methods_remove_required_role(
    method_id: Annotated[UUID, Path(description="Target method's id.")],
    body: RemoveMethodRequiredRoleRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveMethodRequiredRole(
            method_id=method_id,
            role_name=RoleName(body.role_name),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
