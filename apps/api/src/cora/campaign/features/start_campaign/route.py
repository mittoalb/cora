"""HTTP route for the `start_campaign` slice.

Action endpoint at `POST /campaigns/{campaign_id}/start`. 204 No
Content on success. No request body (the transition carries no
operator-supplied fields).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.campaign.features.start_campaign.command import StartCampaign
from cora.campaign.features.start_campaign.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.start_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Campaign exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Campaign is not in Planned status (start_campaign is "
                "single-source from Planned only)."
            ),
        },
    },
    summary="Start a Planned Campaign (Planned -> Active)",
)
async def post_campaigns_start(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        StartCampaign(campaign_id=campaign_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
