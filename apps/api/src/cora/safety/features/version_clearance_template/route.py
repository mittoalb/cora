"""HTTP route for the `version_clearance_template` slice.

Pydantic request body + APIRouter for
`POST /clearance-templates/{template_id}/versions`. Additive within Active:
records that the target template supersedes a parent template, bumping the
monotonic version number by one. No FSM transition. 204 No Content on success.
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
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.safety.features.version_clearance_template.handler import Handler


class VersionClearanceTemplateRequest(BaseModel):
    """Body for `POST /clearance-templates/{template_id}/versions`."""

    new_version: int = Field(
        ...,
        ge=2,
        description=("Monotonic version number to bump to. Must equal current version + 1."),
    )
    supersedes_template_id: UUID = Field(
        ...,
        description=(
            "The parent ClearanceTemplate id this version supersedes. "
            "Must be in the same facility per the cross-facility identity lock."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.version_clearance_template
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearance-templates/{template_id}/versions",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No clearance template exists with the given id, or the "
                "supersedes_template_id parent template was not found."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Template is not in Active status, new_version is not the "
                "current version plus one, or the parent template belongs to "
                "a different facility."
            ),
        },
    },
    summary="Record a new version of an Active clearance template",
)
async def post_clearance_template_versions(
    template_id: Annotated[UUID, Path(description="Target clearance template's id.")],
    body: VersionClearanceTemplateRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VersionClearanceTemplate(
            template_id=template_id,
            new_version=body.new_version,
            supersedes_template_id=body.supersedes_template_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
