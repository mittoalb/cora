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
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_BINDING_ID_MAX_LENGTH,
    CLEARANCE_EXTERNAL_BINDING_SCHEME_MAX_LENGTH,
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    AssetBinding,
    ClearanceBinding,
    ClearanceKind,
    ExternalBinding,
    HazardDeclaration,
    ProcedureBinding,
    RunBinding,
    SubjectBinding,
)
from cora.safety.features.register_clearance.command import RegisterClearance
from cora.safety.features.register_clearance.handler import IdempotentHandler
from cora.safety.hazard_classification import (
    GHS_VALID_PICTOGRAMS,
    NFPA704_MAX_RATING,
    NFPA704_MIN_RATING,
    NFPA704_VALID_SPECIAL,
    SCHEME_CODE_CODE_MAX_LENGTH,
    SCHEME_CODE_SCHEME_MAX_LENGTH,
    SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH,
    GHSPictogram,
    HazardClassification,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)

# ---------------------------------------------------------------------------
# Pydantic DTOs for the discriminated-union wire shapes
# ---------------------------------------------------------------------------


class _BindingSubjectDTO(BaseModel):
    kind: Literal["Subject"]
    id: UUID = Field(..., description="Target Subject's id.")


class _BindingAssetDTO(BaseModel):
    kind: Literal["Asset"]
    id: UUID = Field(..., description="Target Asset's id.")


class _BindingRunDTO(BaseModel):
    kind: Literal["Run"]
    id: UUID = Field(..., description="Target Run's id.")


class _BindingProcedureDTO(BaseModel):
    kind: Literal["Procedure"]
    id: UUID = Field(..., description="Target Procedure's id.")


class _BindingExternalDTO(BaseModel):
    kind: Literal["External"]
    scheme: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_EXTERNAL_BINDING_SCHEME_MAX_LENGTH,
        description=(
            "External-ref scheme: 'proposal' | 'btr' | 'lab_visit' | 'session' "
            "| <future>. Anti-corruption pattern for upstream-deferred concepts "
            "CORA does NOT model (per BC map line 111)."
        ),
    )
    id: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_EXTERNAL_BINDING_ID_MAX_LENGTH,
        description="Facility-minted external ID (e.g. 'GUP-12345').",
    )


_BindingDTO = Annotated[
    _BindingSubjectDTO
    | _BindingAssetDTO
    | _BindingRunDTO
    | _BindingProcedureDTO
    | _BindingExternalDTO,
    Field(discriminator="kind"),
]


class _NFPA704DTO(BaseModel):
    kind: Literal["NFPA704"]
    health: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    flammability: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    instability: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    special: str | None = Field(
        default=None,
        description=(f"Optional NFPA 704 'special' code: one of {sorted(NFPA704_VALID_SPECIAL)}."),
    )


class _RiskBandDTO(BaseModel):
    kind: Literal["RiskBand"]
    band: RiskBand


class _GHSDTO(BaseModel):
    kind: Literal["GHS"]
    code: str = Field(
        ...,
        description=f"GHS pictogram code; one of {sorted(GHS_VALID_PICTOGRAMS)}.",
    )
    statement_codes: list[str] = Field(
        default_factory=list,
        description="GHS H-statement codes triggering this pictogram (e.g. 'H300').",
    )


class _SchemeDTO(BaseModel):
    kind: Literal["Scheme"]
    scheme: str = Field(..., min_length=1, max_length=SCHEME_CODE_SCHEME_MAX_LENGTH)
    code: str = Field(..., min_length=1, max_length=SCHEME_CODE_CODE_MAX_LENGTH)
    severity_label: str = Field(
        default="",
        max_length=SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH,
    )


_ClassificationDTO = Annotated[
    _NFPA704DTO | _RiskBandDTO | _GHSDTO | _SchemeDTO,
    Field(discriminator="kind"),
]


class _HazardDeclarationDTO(BaseModel):
    target: _BindingDTO
    classifications: list[_ClassificationDTO] = Field(default_factory=list[_ClassificationDTO])
    mitigations: list[str] = Field(
        default_factory=list[str],
        description=("Free-form mitigation refs: PPE codes, training cert refs, procedure IDs."),
    )
    notes: str | None = Field(
        default=None,
        max_length=CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    )


class RegisterClearanceRequest(BaseModel):
    """Body for `POST /clearances`."""

    kind: ClearanceKind = Field(
        ...,
        description=("Facility safety-form kind. 12 values covering 9 surveyed facilities."),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_TITLE_MAX_LENGTH,
        description="Operator-readable title for the clearance.",
    )
    bindings: list[_BindingDTO] = Field(
        ...,
        min_length=1,
        description=(
            "Multi-binding: what this clearance gates against. Discriminated "
            "by `kind` ('Subject' | 'Asset' | 'Run' | 'Procedure' | 'External'). "
            "ExternalBinding is the anti-corruption escape hatch for "
            "upstream-deferred refs (proposal / btr / lab_visit / session)."
        ),
    )
    declarations: list[_HazardDeclarationDTO] = Field(
        default_factory=list[_HazardDeclarationDTO],
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
            "Optional facility-minted regulatory ID (e.g. 'ESAF-12345'); "
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
# DTO -> domain conversions
# ---------------------------------------------------------------------------


def _binding_from_dto(dto: _BindingDTO) -> ClearanceBinding:
    if isinstance(dto, _BindingSubjectDTO):
        return SubjectBinding(subject_id=dto.id)
    if isinstance(dto, _BindingAssetDTO):
        return AssetBinding(asset_id=dto.id)
    if isinstance(dto, _BindingRunDTO):
        return RunBinding(run_id=dto.id)
    if isinstance(dto, _BindingProcedureDTO):
        return ProcedureBinding(procedure_id=dto.id)
    return ExternalBinding(scheme=dto.scheme, id=dto.id)


def _classification_from_dto(dto: _ClassificationDTO) -> HazardClassification:
    if isinstance(dto, _NFPA704DTO):
        return NFPA704Rating(
            health=dto.health,
            flammability=dto.flammability,
            instability=dto.instability,
            special=dto.special,
        )
    if isinstance(dto, _RiskBandDTO):
        return dto.band
    if isinstance(dto, _GHSDTO):
        return GHSPictogram(
            code=dto.code,
            statement_codes=frozenset(dto.statement_codes),
        )
    return SchemeCode(
        scheme=dto.scheme,
        code=dto.code,
        severity_label=dto.severity_label,
    )


def _declaration_from_dto(dto: _HazardDeclarationDTO) -> HazardDeclaration:
    return HazardDeclaration(
        target=_binding_from_dto(dto.target),
        classifications=frozenset(_classification_from_dto(c) for c in dto.classifications),
        mitigations=frozenset(dto.mitigations),
        notes=dto.notes,
    )


def _command_from_request(body: RegisterClearanceRequest) -> RegisterClearance:
    return RegisterClearance(
        kind=body.kind,
        title=body.title,
        bindings=frozenset(_binding_from_dto(b) for b in body.bindings),
        declarations=frozenset(_declaration_from_dto(d) for d in body.declarations),
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
        idempotency_key=idempotency_key,
    )
    return RegisterClearanceResponse(clearance_id=clearance_id)
