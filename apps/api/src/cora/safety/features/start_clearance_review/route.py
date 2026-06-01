"""HTTP route for the `start_clearance_review` slice.

Action endpoint at `POST /clearances/{clearance_id}/start-review`.
Body carries `first_reviewer_role`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.start_clearance_review.command import StartClearanceReview
from cora.safety.features.start_clearance_review.handler import Handler


class StartClearanceReviewRequest(BaseModel):
    """Body for `POST /clearances/{clearance_id}/start-review`."""

    first_reviewer_role: str = Field(
        ...,
        min_length=1,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        description=(
            "Facility-vocabulary label for the first reviewer in the chain "
            "(for example, 'BeamlineScientist', 'LocalContact', 'ESH', 'ESRB')."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.start_clearance_review
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/start-review",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only role).",
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
                "Clearance is not in Submitted status (start_clearance_review "
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
    body: StartClearanceReviewRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        StartClearanceReview(
            clearance_id=clearance_id,
            first_reviewer_role=body.first_reviewer_role,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
