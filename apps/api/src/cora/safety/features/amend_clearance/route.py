"""HTTP route for the `amend_clearance` slice.

Action endpoint at `POST /clearances/{parent_id}/amend`.
Body carries the child clearance's full fields (kind, facility,
title, bindings, declarations, risk_band, external_id?, valid_from?,
valid_until?). Returns 201 + the new child's clearance_id.

Reuses `register_clearance`'s discriminated-union DTOs
(`BindingDTO`, `ClassificationDTO`, `HazardDeclarationDTO`) plus
its DTO->domain converters since the child IS a registration. The
parent id comes from the URL path. The amending-actor id comes from
the request's authenticated principal via the event envelope.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety._clearance_dtos import (
    BindingDTO,
    HazardDeclarationDTO,
    binding_from_dto,
    declaration_from_dto,
)
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    ClearanceKind,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.features.amend_clearance.command import AmendClearance
from cora.safety.features.amend_clearance.handler import IdempotentHandler


class AmendClearanceRequest(BaseModel):
    """Body for `POST /clearances/{parent_id}/amend`.

    Mirrors `RegisterClearanceRequest`'s child-fields exactly. The
    `parent_id` comes from the URL path, not the body.
    """

    kind: ClearanceKind = Field(
        ...,
        description="Form-type for the child clearance (may differ from parent's).",
    )
    facility_code: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=(
            "Cross-deployment convergent slug for the Federation Facility "
            "issuing the child clearance. Typically matches the parent's facility."
        ),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_TITLE_MAX_LENGTH,
        description="Operator-readable title for the child clearance.",
    )
    bindings: list[BindingDTO] = Field(
        ...,
        min_length=1,
        description="Child's bindings; same discriminated-union shape as register_clearance.",
    )
    declarations: list[HazardDeclarationDTO] = Field(
        default_factory=list[HazardDeclarationDTO],
        description="Child's hazard declarations; empty list allowed.",
    )
    risk_band: RiskBand | None = Field(default=None)
    external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    )
    valid_from: datetime | None = Field(default=None)
    valid_until: datetime | None = Field(default=None)


class AmendClearanceResponse(BaseModel):
    """Response body for `POST /clearances/{parent_id}/amend`."""

    clearance_id: UUID = Field(..., description="The new child clearance's id.")


def _command_from_request(
    parent_id: UUID,
    body: AmendClearanceRequest,
) -> AmendClearance:
    return AmendClearance(
        parent_id=parent_id,
        kind=body.kind,
        facility_code=body.facility_code,
        title=body.title,
        bindings=frozenset(binding_from_dto(b) for b in body.bindings),
        declarations=frozenset(declaration_from_dto(d) for d in body.declarations),
        risk_band=body.risk_band,
        external_id=body.external_id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
    )


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.safety.amend_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{parent_id}/amend",
    status_code=status.HTTP_201_CREATED,
    response_model=AmendClearanceResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated on the child's fields (whitespace-"
                "only title, empty bindings, inverted validity window, etc.) "
                "OR the parent's binding declarations cross-validation failed."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No parent clearance exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Parent is not in Active status (amend_clearance is single-"
                "source from Active only) OR optimistic-concurrency conflict "
                "on the parent stream (concurrent transition; retry)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation, OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Amend an Active clearance (atomic parent:Active->Superseded + child:Defined)",
)
async def post_clearances_amend(
    parent_id: Annotated[UUID, Path(description="Parent clearance's id.")],
    body: AmendClearanceRequest,
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
                "response instead of re-creating the child clearance."
            ),
        ),
    ] = None,
) -> AmendClearanceResponse:
    child_clearance_id = await handler(
        _command_from_request(parent_id, body),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return AmendClearanceResponse(clearance_id=child_clearance_id)
