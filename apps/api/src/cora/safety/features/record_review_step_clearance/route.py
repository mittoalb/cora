"""HTTP route for the `record_review_step_clearance` slice.

Action endpoint at `POST /clearances/{clearance_id}/review_steps`.
Body carries one ReviewerStep's worth of data. The reviewing-actor id
is filled from the request's authenticated principal. 204 on success.

`step_index` is REQUIRED in the body so callers explicitly assert
which position in the chain they are appending to (idempotency-friendly:
re-issuing the same step_index detects out-of-order writes via the
decider's `step_index == len(state.reviewers)` invariant).
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.record_review_step_clearance.command import (
    RecordReviewStepClearance,
)
from cora.safety.features.record_review_step_clearance.handler import Handler


class RecordReviewStepClearanceRequest(BaseModel):
    """Body for `POST /clearances/{clearance_id}/review_steps`."""

    step_index: int = Field(
        ...,
        ge=0,
        description=(
            "0-based step index. MUST equal `len(reviewers)` at append time "
            "(append-only contract); out-of-order writes return 400."
        ),
    )
    role: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        description="Facility-vocabulary reviewer role.",
    )
    decision: Literal["Approved", "Rejected", "RequestedChanges"] = Field(
        ...,
        description=(
            "Reviewer decision for this step. 'Approved' / 'Rejected' are "
            "non-terminal at the chain level; the chain continues until "
            "`approve_clearance` / `reject_clearance` consume the chain."
        ),
    )
    decided_at: datetime = Field(
        ...,
        description="Operator-supplied timestamp when the reviewer made the decision.",
    )
    notes: str | None = Field(
        default=None,
        max_length=CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
        description="Optional reviewer notes (audit breadcrumb).",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.record_review_step_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/review_steps",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only role / oversized "
                "notes / wrong step_index for append-only contract)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Clearance is not in UnderReview status "
                "(record_review_step is single-source from UnderReview only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing fields, "
                "decision not in {Approved, Rejected, RequestedChanges}, "
                "negative step_index, malformed datetime)."
            ),
        },
    },
    summary="Append one reviewer step to an UnderReview clearance's chain",
)
async def post_clearances_review_steps(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    body: RecordReviewStepClearanceRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        RecordReviewStepClearance(
            clearance_id=clearance_id,
            step_index=body.step_index,
            role=body.role,
            actor_id=principal_id,
            decision=body.decision,
            decided_at=body.decided_at,
            notes=body.notes,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
