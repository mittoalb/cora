"""HTTP route for the `get_clearance_template` query slice.

`GET /clearance-templates/{template_id}` returns 200 +
ClearanceTemplateResponse on hit, 404 on miss. The handler returns
`ClearanceTemplate | None`; the route maps None to 404 via
HTTPException (idiomatic in routes; the BC's exception-handler
infrastructure stays focused on domain / application errors raised
deeper in the stack).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
)
from cora.safety.features.get_clearance_template.handler import Handler
from cora.safety.features.get_clearance_template.query import GetClearanceTemplate


class ClearanceTemplateResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `status` is the StrEnum's string value (Draft / Active /
    Deprecated / Withdrawn). `version` is the monotonic version
    number of the most recent `version_clearance_template` call
    (default 1 on genesis). `supersedes_template_id` references
    the prior version in the chain (null on first definition).
    `external_ref` is the optional facility-minted identifier
    (null until assigned).
    """

    id: UUID
    code: str = Field(..., max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH)
    title: str = Field(..., max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH)
    facility_code: str
    version: int
    supersedes_template_id: UUID | None
    external_ref: str | None = Field(
        default=None, max_length=CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH
    )
    status: str
    defined_at: str
    defined_by: str


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.get_clearance_template
    return handler


router = APIRouter(tags=["safety"])


@router.get(
    "/clearance-templates/{template_id}",
    status_code=status.HTTP_200_OK,
    response_model=ClearanceTemplateResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance template exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a clearance template by id",
)
async def get_clearance_template_endpoint(
    template_id: Annotated[UUID, Path(description="Target clearance template's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ClearanceTemplateResponse:
    template = await handler(
        GetClearanceTemplate(template_id=template_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clearance template {template_id} not found",
        )
    return ClearanceTemplateResponse(
        id=template.id,
        code=template.code.value,
        title=template.title.value,
        facility_code=template.facility_code.value,
        version=template.version.value,
        supersedes_template_id=template.supersedes_template_id,
        external_ref=template.external_ref,
        status=template.status.value,
        defined_at=template.defined_at.isoformat(),
        defined_by=str(template.defined_by),
    )
