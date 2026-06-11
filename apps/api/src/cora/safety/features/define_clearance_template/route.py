"""HTTP route for the `define_clearance_template` slice.

Pydantic request/response schemas + APIRouter for `POST /clearance-templates`.
The slice's BC-level wiring (`cora.safety.routes.register_safety_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
)
from cora.safety.features.define_clearance_template.command import (
    DefineClearanceTemplate,
)
from cora.safety.features.define_clearance_template.handler import IdempotentHandler


class DefineClearanceTemplateRequest(BaseModel):
    """Body for `POST /clearance-templates`."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
        description=(
            "Machine-readable code for the template "
            "(facility-scoped; 1-50 chars after trim, e.g. 'ESAF', 'SAF')."
        ),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
        description="Display name for the new ClearanceTemplate.",
    )
    facility_code: str = Field(
        ...,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=("Facility code (cross-deployment convergent slug) this template belongs to."),
    )
    external_ref: str | None = Field(
        default=None,
        description="Optional external reference (e.g., upstream document identifier).",
    )


class DefineClearanceTemplateResponse(BaseModel):
    """Response body for `POST /clearance-templates`."""

    template_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.safety.define_clearance_template
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearance-templates",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineClearanceTemplateResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g., whitespace-only code or title).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Facility code not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Template (facility_code, code) already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new safety clearance template",
)
async def post_clearance_templates(
    body: DefineClearanceTemplateRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the template."
            ),
        ),
    ] = None,
) -> DefineClearanceTemplateResponse:
    template_id = await handler(
        DefineClearanceTemplate(
            code=body.code,
            title=body.title,
            facility_code=body.facility_code,
            external_ref=body.external_ref,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineClearanceTemplateResponse(template_id=template_id)
