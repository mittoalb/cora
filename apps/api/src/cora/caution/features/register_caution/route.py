"""HTTP route for the `register_caution` slice.

Pydantic request/response schemas + APIRouter for `POST /cautions`.
The slice's BC-level wiring (`cora.caution.routes.register_caution_routes`)
includes this router on the FastAPI app.

Polymorphic `target` field uses the shared `TargetDTO` (discriminated
union of `TargetAssetDTO` / `TargetProcedureDTO`) from
`cora.caution._caution_dtos` to keep the wire shape consistent
between `register_caution` and `supersede_caution`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.caution._caution_dtos import TargetDTO, target_from_dto
from cora.caution.aggregates.caution import (
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution.command import RegisterCaution
from cora.caution.features.register_caution.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RegisterCautionRequest(BaseModel):
    """Body for `POST /cautions`."""

    target: TargetDTO = Field(
        ...,
        description=(
            "Polymorphic target: `{kind: 'Asset', id: <uuid>}` or "
            "`{kind: 'Procedure', id: <uuid>}`. Day-1 lock; Run + Subject "
            "variants land additively per design memo Watch items."
        ),
    )
    category: CautionCategory = Field(
        ...,
        description=(
            "Closed controlled-vocabulary category. One of Wear, Calibration, "
            "Wiring, OperationalWindow, InterlockQuirk, ProcedureGotcha."
        ),
    )
    severity: CautionSeverity = Field(
        ...,
        description=(
            "ANSI Z535 signal-word ladder (downshifted). One of Notice, "
            "Caution, Warning. No Danger tier; formal lockout lives in Safety BC."
        ),
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=CAUTION_TEXT_MAX_LENGTH,
        description=("Free-form caution body. Trimmed at the domain layer."),
    )
    workaround: str = Field(
        ...,
        min_length=1,
        max_length=CAUTION_WORKAROUND_MAX_LENGTH,
        description=(
            "REQUIRED. Free-form 'what does the operator do about it' field "
            "(corpus's strongest convergence: KEDB, MIL-STD-882, OSHA, CAPA "
            "all mandate it). Trimmed at the domain layer."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "Optional free-form tags. Each tag 1-50 chars after trim. Empty list IS allowed."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "Optional auto-retire hint. Must be strictly in the future "
            "(relative to server clock at register time)."
        ),
    )
    propagate_to_children: bool = Field(
        default=False,
        description=(
            "Opt-in for Asset-hierarchy inheritance (AVEVA AF template-"
            "inheritance anti-pattern guard). Default False."
        ),
    )


class RegisterCautionResponse(BaseModel):
    """Response body for `POST /cautions`."""

    caution_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.caution.register_caution
    return handler


router = APIRouter(tags=["caution"])


@router.post(
    "/cautions",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterCautionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only text / workaround / "
                "tag, past-dated expires_at, or supersede-target mismatch)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target caution stream already has events. "
                "Essentially impossible in production with UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid enum, length out of bounds, malformed target "
                "discriminator), OR Idempotency-Key was reused with a "
                "different request body."
            ),
        },
    },
    summary="Register a new caution (lands in Active)",
)
async def post_cautions(
    body: RegisterCautionRequest,
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
                "response instead of re-creating the caution."
            ),
        ),
    ] = None,
) -> RegisterCautionResponse:
    caution_id = await handler(
        RegisterCaution(
            target=target_from_dto(body.target),
            category=body.category,
            severity=body.severity,
            text=body.text,
            workaround=body.workaround,
            tags=frozenset(body.tags),
            expires_at=body.expires_at,
            propagate_to_children=body.propagate_to_children,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterCautionResponse(caution_id=caution_id)
