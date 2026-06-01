"""HTTP route for the `add_run_to_campaign` slice.

Action endpoint at `POST /campaigns/{campaign_id}/runs/{run_id}/add`.
No body. 204 No Content on success. Both ids come from the URL path.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.campaign.features.add_run_to_campaign.command import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.add_run_to_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/runs/{run_id}/add",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Campaign or Run does not exist.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Campaign is in a terminal status (Closed / Abandoned) and "
                "refuses new members, OR the Run is already a member of this "
                "Campaign, OR the Run is already assigned to a different "
                "Campaign, OR an optimistic-concurrency conflict on either "
                "stream (concurrent transition; retry)."
            ),
        },
    },
    summary="Add a Run as a member of a Campaign (atomic two-stream write)",
)
async def post_campaign_runs_add(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    run_id: Annotated[UUID, Path(description="Run to add as a member.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
