"""HTTP route for the `get_campaign` query slice.

`GET /campaigns/{campaign_id}` returns 200 + CampaignResponse on hit,
404 on miss. The handler returns `Campaign | None`; the route maps
None to 404 via HTTPException (idiomatic in routes; the BC's
exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignIntent,
    CampaignStatus,
)
from cora.campaign.features.get_campaign.handler import Handler
from cora.campaign.features.get_campaign.query import GetCampaign
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class ExternalRefDTO(BaseModel):
    """Wire shape for an ExternalRef in the GET response."""

    scheme: str
    id: str


class CampaignResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.

    `run_ids` / `tags` / `external_refs` are sorted for deterministic
    bytes on read (helps response-shape stability for clients that
    diff responses; also harmonises with how events serialise the
    same fields).
    """

    id: UUID
    name: str
    intent: CampaignIntent
    lead_actor_id: UUID
    subject_id: UUID | None
    description: str | None
    tags: list[str]
    external_refs: list[ExternalRefDTO]
    external_id: str | None
    run_ids: list[UUID]
    status: CampaignStatus
    last_status_reason: str | None = Field(
        default=None,
        description=(
            "Operator-supplied audit breadcrumb from the last Held or "
            "Abandoned transition. Preserved across Resume so the "
            "'why was it held?' answer stays readable."
        ),
    )


def _response_from_state(campaign: Campaign) -> CampaignResponse:
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name.value,
        intent=campaign.intent,
        lead_actor_id=campaign.lead_actor_id,
        subject_id=campaign.subject_id,
        description=campaign.description.value if campaign.description is not None else None,
        tags=sorted(t.value for t in campaign.tags),
        external_refs=[
            ExternalRefDTO(scheme=r.scheme, id=r.id)
            for r in sorted(campaign.external_refs, key=lambda r: (r.scheme, r.id))
        ],
        external_id=campaign.external_id,
        run_ids=sorted(campaign.run_ids),
        status=campaign.status,
        last_status_reason=campaign.last_status_reason,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.get_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.get(
    "/campaigns/{campaign_id}",
    status_code=status.HTTP_200_OK,
    response_model=CampaignResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Campaign exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a Campaign by id",
)
async def get_campaigns(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> CampaignResponse:
    campaign = await handler(
        GetCampaign(campaign_id=campaign_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )
    return _response_from_state(campaign)
