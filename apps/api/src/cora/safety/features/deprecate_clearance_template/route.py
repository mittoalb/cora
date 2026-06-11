"""HTTP route for the `deprecate_clearance_template` slice.

Action endpoint at `POST /clearance-templates/{template_id}/deprecate`. No
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
from cora.safety.features.deprecate_clearance_template.command import (
    DeprecateClearanceTemplate,
)
from cora.safety.features.deprecate_clearance_template.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.deprecate_clearance_template
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearance-templates/{template_id}/deprecate",
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
                "Clearance template is not in Active status "
                "(deprecate_clearance_template is single-source from Active only)."
            ),
        },
    },
    summary="Deprecate an Active clearance template (Active -> Deprecated)",
)
async def post_clearance_templates_deprecate(
    template_id: Annotated[UUID, Path(description="Target clearance template's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecateClearanceTemplate(template_id=template_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
