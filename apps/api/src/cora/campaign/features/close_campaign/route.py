"""HTTP route for the `close_campaign` slice.

Action endpoint at `POST /campaigns/{campaign_id}/close`. 204 No
Content on success. No request body.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.campaign.features.close_campaign.command import CloseCampaign
from cora.campaign.features.close_campaign.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.close_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/close",
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
                "Campaign is not in a closable status. Source set: "
                "{Active, Held}. Closed / Abandoned terminals refuse "
                "re-close; Planned refuses (work never started)."
            ),
        },
    },
    summary="Close a Campaign (Active | Held -> Closed)",
)
async def post_campaigns_close(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        CloseCampaign(campaign_id=campaign_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
