"""HTTP route for the `get_clearance` query slice.

`GET /clearances/{clearance_id}` returns 200 + ClearanceResponse on hit,
404 on miss. The handler returns `Clearance | None`; the route maps
None to 404 via HTTPException (idiomatic in routes).

The response uses `dict[str, Any]` for the polymorphic `bindings`,
`declarations`, and `reviewers` fields. Each item in those lists is a
JSON object whose `kind` discriminator selects the variant shape; the
serialization helpers from `cora.safety.aggregates.clearance.events`
produce the exact same shape used in the event payloads, so the wire
format is consistent between create-side and read-side.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    Clearance,
    ClearanceKind,
    ClearanceStatus,
    ReviewerStep,
)
from cora.safety.aggregates.clearance.events import (
    serialize_binding,
    serialize_declaration,
)
from cora.safety.features.get_clearance.handler import Handler
from cora.safety.features.get_clearance.query import GetClearance
from cora.safety.hazard_classification import RiskBand


class ReviewerStepResponse(BaseModel):
    """One step in the reviewer chain on the wire."""

    step_index: int
    role: str
    actor_id: UUID
    decision: str
    decided_at: datetime
    notes: str | None = None


class ClearanceResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives + JSON dicts (for polymorphic fields), not domain
    VOs. Decouples the wire format from the domain model so the two can
    evolve independently.

    `bindings`, `declarations` are JSON lists; each item is a dict whose
    `kind` discriminator selects the variant shape (Subject / Asset /
    Run / Procedure / External for bindings; NFPA704 / RiskBand / GHS /
    Scheme for classifications).
    """

    id: UUID
    kind: ClearanceKind
    facility_asset_id: UUID
    title: str = Field(..., max_length=CLEARANCE_TITLE_MAX_LENGTH)
    bindings: list[dict[str, Any]]
    declarations: list[dict[str, Any]]
    risk_band: RiskBand | None = None
    reviewers: list[ReviewerStepResponse]
    status: ClearanceStatus
    external_id: str | None = Field(default=None, max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH)
    parent_clearance_id: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_due_at: datetime | None = None
    last_reviewed_by_actor_id: UUID | None = None


def _reviewer_step_to_response(step: ReviewerStep) -> ReviewerStepResponse:
    return ReviewerStepResponse(
        step_index=step.step_index,
        role=step.role,
        actor_id=step.actor_id,
        decision=step.decision,
        decided_at=step.decided_at,
        notes=step.notes,
    )


def _clearance_to_response(clearance: Clearance) -> ClearanceResponse:
    return ClearanceResponse(
        id=clearance.id,
        kind=clearance.kind,
        facility_asset_id=clearance.facility_asset_id,
        title=clearance.title.value,
        bindings=[serialize_binding(b) for b in clearance.bindings],
        declarations=[serialize_declaration(d) for d in clearance.declarations],
        risk_band=clearance.risk_band,
        reviewers=[_reviewer_step_to_response(r) for r in clearance.reviewers],
        status=clearance.status,
        external_id=clearance.external_id,
        parent_clearance_id=clearance.parent_clearance_id,
        valid_from=clearance.valid_from,
        valid_until=clearance.valid_until,
        next_review_due_at=clearance.next_review_due_at,
        last_reviewed_by_actor_id=clearance.last_reviewed_by_actor_id,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.get_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.get(
    "/clearances/{clearance_id}",
    status_code=status.HTTP_200_OK,
    response_model=ClearanceResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a clearance by id",
)
async def get_clearances(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> ClearanceResponse:
    clearance = await handler(
        GetClearance(clearance_id=clearance_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if clearance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clearance {clearance_id} not found",
        )
    return _clearance_to_response(clearance)
