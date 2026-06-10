"""HTTP route for the `activate_clearance_template` slice.

Action endpoint at `POST /clearance-templates/{template_id}/activate`. No
body fields. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety.features.activate_clearance_template.command import (
    ActivateClearanceTemplate,
)
from cora.safety.features.activate_clearance_template.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.activate_clearance_template
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearance-templates/{template_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance template exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Clearance template is not in Draft status "
                "(activate_clearance_template is single-source from Draft only)."
            ),
        },
    },
    summary="Activate a Draft clearance template (Draft -> Active)",
)
async def post_clearance_templates_activate(
    template_id: Annotated[UUID, Path(description="Target clearance template's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ActivateClearanceTemplate(template_id=template_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
