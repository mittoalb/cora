"""HTTP route for the `approve_clearance` slice.

Action endpoint at `POST /clearances/{clearance_id}/approve`. Body
optionally carries `valid_from` / `valid_until` to refine the
validity window. The approving-actor id is filled from the request's
authenticated principal. 204 No Content on success.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.safety.features.approve_clearance.command import ApproveClearance
from cora.safety.features.approve_clearance.handler import Handler


class ApproveClearanceRequest(BaseModel):
    """Body for `POST /clearances/{clearance_id}/approve`."""

    valid_from: datetime | None = Field(
        default=None,
        description="Optional override of the effective-from timestamp.",
    )
    valid_until: datetime | None = Field(
        default=None,
        description=(
            "Optional override of the effective-until timestamp. Must be "
            "strictly greater than `valid_from` when both are provided."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.approve_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (inverted or zero-duration validity "
                "window). The 'no approving reviewer step recorded' case "
                "returns 409, not 400 (see ClearanceCannotApproveError)."
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
                "Clearance is not in UnderReview status (approve_clearance "
                "is single-source from UnderReview only), OR no reviewer "
                "step in the chain has decision='Approved'."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Approve an UnderReview clearance (UnderReview -> Approved)",
)
async def post_clearances_approve(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    body: ApproveClearanceRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        ApproveClearance(
            clearance_id=clearance_id,
            approving_actor_id=principal_id,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
