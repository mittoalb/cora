"""HTTP route for the `retire_caution` slice.

Action endpoint at `POST /cautions/{caution_id}/retire`. Body
carries `reason` (closed `CautionRetireReason` enum: Resolved /
NoLongerApplies / WrongTarget). 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.caution.aggregates.caution import CautionRetireReason
from cora.caution.features.retire_caution.command import RetireCaution
from cora.caution.features.retire_caution.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RetireCautionRequest(BaseModel):
    """Body for `POST /cautions/{caution_id}/retire`."""

    reason: CautionRetireReason = Field(
        ...,
        description=(
            "Closed reason enum: Resolved (underlying condition fixed), "
            "NoLongerApplies (asset removed / scope changed), or "
            "WrongTarget (caution was attached to wrong Asset / Procedure)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.caution.retire_caution
    return handler


router = APIRouter(tags=["caution"])


@router.post(
    "/cautions/{caution_id}/retire",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No caution exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Caution is not in Active status (retire_caution is single-"
                "source from Active only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation (unknown reason).",
        },
    },
    summary="Retire an Active caution (Active -> Retired)",
)
async def post_cautions_retire(
    caution_id: Annotated[UUID, Path(description="Target caution's id.")],
    body: RetireCautionRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RetireCaution(
            caution_id=caution_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
