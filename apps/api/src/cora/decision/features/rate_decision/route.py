"""HTTP route for the `rate_decision` slice (Phase 8f-b iter 1).

Action endpoint at `POST /decisions/{decision_id}/ratings`. Body
carries `rating` (closed `DecisionRating` enum: useful / misleading
/ ignored) and optional `comment` (1-2000 chars after trim if
provided; null to omit). 204 No Content on success.

Multiple ratings per (decision, actor) pair are allowed; latest
wins in the projection. NOT idempotency-wrapped.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.decision.aggregates.decision import (
    DECISION_RATING_COMMENT_MAX_LENGTH,
    DecisionRating,
)
from cora.decision.features.rate_decision.command import RateDecision
from cora.decision.features.rate_decision.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RateDecisionRequest(BaseModel):
    """Body for `POST /decisions/{decision_id}/ratings`."""

    rating: DecisionRating = Field(
        ...,
        description=(
            "Closed rating value: `useful` (decision helped), "
            "`misleading` (decision led astray), or `ignored` "
            "(operator saw the decision and chose not to act). "
            "Note `ignored` is a positive marker, distinct from "
            "no-rating-at-all."
        ),
    )
    comment: str | None = Field(
        default=None,
        min_length=1,
        max_length=DECISION_RATING_COMMENT_MAX_LENGTH,
        description=(
            "Optional free-form comment (1-2000 chars after trim). "
            "Pass null to omit; do not pass empty string."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.decision.rate_decision
    return handler


router = APIRouter(tags=["decision"])


@router.post(
    "/decisions/{decision_id}/ratings",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Comment failed domain validation (empty / whitespace-"
                "only after trim, or over-cap after trim)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Decision exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (unknown rating "
                "value, comment length out of bounds, malformed UUID)."
            ),
        },
    },
    summary="Rate a Decision (operator acceptance-signal capture)",
)
async def post_decisions_ratings(
    decision_id: Annotated[UUID, Path(description="Target Decision's id.")],
    body: RateDecisionRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RateDecision(
            decision_id=decision_id,
            rating=body.rating,
            comment=body.comment,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
