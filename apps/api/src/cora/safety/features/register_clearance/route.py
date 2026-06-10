"""HTTP route for the `register_clearance` slice.

Pydantic request/response schemas + APIRouter for `POST /clearances`.
The slice's BC-level wiring (`cora.safety.routes.register_safety_routes`)
includes this router on the FastAPI app.

The discriminated-union shapes (HazardClassification, ClearanceBinding)
are accepted at the API as `kind`-tagged objects and converted to typed
VOs in `_command_from_request` before reaching the handler. Pydantic
validates the wire shape; the route function constructs the domain
objects.
"""

from datetime import datetime
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
from cora.safety._clearance_dtos import (
    BindingDTO,
    HazardDeclarationDTO,
    binding_from_dto,
    declaration_from_dto,
)
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.aggregates.clearance_template import ClearanceTemplateId
from cora.safety.features.register_clearance.command import RegisterClearance
from cora.safety.features.register_clearance.handler import IdempotentHandler


class RegisterClearanceRequest(BaseModel):
    """Body for `POST /clearances`."""

    template_id: UUID = Field(
        ...,
        description=(
            "ClearanceTemplate id (Safety BC; auto-seeded per facility). The "
            "handler resolves via ClearanceTemplateLookup; only Active templates "
            "are bindable (404 on unknown id, 409 on non-Active status)."
        ),
    )
    facility_code: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=(
            "Cross-deployment convergent slug for the Federation Facility that "
            "issued (or will issue) this clearance. Resolved at handler time via "
            "FacilityLookup.lookup_by_code; an unknown code surfaces as 404."
        ),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_TITLE_MAX_LENGTH,
        description="Operator-readable title for the clearance.",
    )
    bindings: list[BindingDTO] = Field(
        ...,
        min_length=1,
        description=(
            "Multi-binding: what this clearance gates against. Discriminated "
            "by `kind` ('Subject' | 'Asset' | 'Run' | 'Procedure' | 'External'). "
            "ExternalRefBinding is the anti-corruption escape hatch for "
            "upstream-deferred refs (proposal / btr / lab_visit / session)."
        ),
    )
    declarations: list[HazardDeclarationDTO] = Field(
        default_factory=list[HazardDeclarationDTO],
        description=(
            "Hazard claims (intrinsic descriptor + mitigations) per binding "
            "target. Empty list allowed."
        ),
    )
    risk_band: RiskBand | None = Field(
        default=None,
        description=(
            "Optional triage band (Green / Yellow / Red) per HSE ALARP "
            "semantics. Used by ESRF / MAX IV / DLS / DESY / SLAC variants; "
            "None for APS-style ESAF."
        ),
    )
    external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
        description=(
            "Optional facility-minted regulatory ID (for example 'ESAF-12345'); "
            "lazy-mint per the PID landscape pattern."
        ),
    )
    valid_from: datetime | None = Field(
        default=None,
        description=(
            "Effective-from timestamp; ISO-8601 on the wire, parsed by Pydantic. "
            "Malformed values 422; tz-naive timestamps are accepted but discouraged."
        ),
    )
    valid_until: datetime | None = Field(
        default=None,
        description=(
            "Effective-until timestamp; ISO-8601 on the wire, parsed by Pydantic. "
            "Must be strictly greater than `valid_from` "
            "(zero-duration windows rejected at decider)."
        ),
    )


class RegisterClearanceResponse(BaseModel):
    """Response body for `POST /clearances`."""

    clearance_id: UUID


# ---------------------------------------------------------------------------
# DTO -> domain conversion
# ---------------------------------------------------------------------------


def _command_from_request(body: RegisterClearanceRequest) -> RegisterClearance:
    return RegisterClearance(
        template_id=ClearanceTemplateId(body.template_id),
        facility_code=body.facility_code,
        title=body.title,
        bindings=frozenset(binding_from_dto(b) for b in body.bindings),
        declarations=frozenset(declaration_from_dto(d) for d in body.declarations),
        risk_band=body.risk_band,
        external_id=body.external_id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.safety.register_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterClearanceResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only title, empty "
                "bindings, inverted validity window, oversized mitigation ref, "
                "etc.)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target clearance stream already has events. "
                "Essentially impossible in production with UUIDv7 ids; documented "
                "for OpenAPI completeness against the BC's exception handler."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid enum, length out of bounds, malformed datetime, "
                "invalid NFPA 704 quadrant), OR Idempotency-Key was reused "
                "with a different request body."
            ),
        },
    },
    summary="Register a new safety-form clearance (lands in Defined)",
)
async def post_clearances(
    body: RegisterClearanceRequest,
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
                "response instead of re-creating the clearance."
            ),
        ),
    ] = None,
) -> RegisterClearanceResponse:
    clearance_id = await handler(
        _command_from_request(body),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterClearanceResponse(clearance_id=clearance_id)
