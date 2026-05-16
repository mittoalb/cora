"""HTTP route for the `resume_campaign` slice.

Action endpoint at `POST /campaigns/{campaign_id}/resume`. 204 No
Content on success. No request body.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.campaign.features.resume_campaign.command import ResumeCampaign
from cora.campaign.features.resume_campaign.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.resume_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/resume",
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
                "Campaign is not in Held status (resume_campaign is single-source from Held only)."
            ),
        },
    },
    summary="Resume a Held Campaign (Held -> Active)",
)
async def post_campaigns_resume(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        ResumeCampaign(campaign_id=campaign_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
