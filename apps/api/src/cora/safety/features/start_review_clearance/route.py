"""HTTP route for the `start_review_clearance` slice.

Action endpoint at `POST /clearances/{clearance_id}/start_review`.
Body carries `first_reviewer_role`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.start_review_clearance.command import StartReviewClearance
from cora.safety.features.start_review_clearance.handler import Handler


class StartReviewClearanceRequest(BaseModel):
    """Body for `POST /clearances/{clearance_id}/start_review`."""

    first_reviewer_role: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        description=(
            "Facility-vocabulary label for the first reviewer in the chain "
            "(e.g., 'BeamlineScientist', 'LocalContact', 'ESH', 'ESRB')."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.start_review_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/start_review",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g. whitespace-only role).",
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
                "Clearance is not in Submitted status (start_review_clearance "
                "is single-source from Submitted only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing first_reviewer_role, "
                "empty, or exceeds 50 chars)."
            ),
        },
    },
    summary="Start reviewing a Submitted clearance (Submitted -> UnderReview)",
)
async def post_clearances_start_review(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    body: StartReviewClearanceRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        StartReviewClearance(
            clearance_id=clearance_id,
            first_reviewer_role=body.first_reviewer_role,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
