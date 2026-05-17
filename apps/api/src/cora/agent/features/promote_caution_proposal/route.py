"""HTTP route for the `promote_caution_proposal` slice.

Operator-triggered cross-BC promotion endpoint at
`POST /agents/caution_drafter/decisions/{decision_id}/promote`.
No request body (the proposed-Caution payload is carried by the
referenced Decision's `inputs`).

Returns the new Caution's id on success (201 Created with
`{"caution_id": "<uuid>"}`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel

from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
)


class PromoteCautionProposalResponse(BaseModel):
    """Successful promotion response body."""

    caution_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.agent.promote_caution_proposal
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/caution_drafter/decisions/{decision_id}/promote",
    status_code=status.HTTP_201_CREATED,
    response_model=PromoteCautionProposalResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Decision has wrong context, is non-actionable (NoAction), "
                "or carries a malformed `proposed_caution` payload."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": (
                "Authorize port denied the command, OR the Decision was not "
                "emitted by a registered CautionDrafter agent (provenance gate)."
            ),
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Decision exists with the given id, or the referenced "
                "Caution (for ProposeSupersede) does not exist."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "ProposeSupersede target Caution is not in Active.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary=(
        "Promote a CautionProposal Decision into a real Caution (cross-BC write to Caution BC)"
    ),
)
async def post_promote_caution_proposal(
    decision_id: Annotated[UUID, Path(description="Target Decision's id.")],
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Brandur-style idempotency key (optional).",
        ),
    ] = None,
) -> PromoteCautionProposalResponse:
    caution_id = await handler(
        PromoteCautionProposal(decision_id=decision_id),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return PromoteCautionProposalResponse(caution_id=caution_id)
