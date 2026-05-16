"""MCP tool for the `get_campaign` query slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. On miss the tool raises ValueError so FastMCP
wraps the response as `isError: true` with a clear diagnostic, same
convention as `get_caution` / `get_supply` / `get_clearance`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.aggregates.campaign import CampaignIntent, CampaignStatus
from cora.campaign.features.get_campaign.handler import Handler
from cora.campaign.features.get_campaign.query import GetCampaign
from cora.infrastructure.observability import current_correlation_id


class ExternalRefDTO(BaseModel):
    scheme: str
    id: str


class CampaignOutput(BaseModel):
    """Structured output of the `get_campaign` MCP tool (on hit)."""

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
    last_status_reason: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="get_campaign",
        description=(
            "Look up a Campaign by id. Returns name, intent, lead actor, "
            "optional subject, description, tags, external refs, member "
            "run ids, and current FSM status (Planned / Active / Held / "
            "Closed / Abandoned) plus the last_status_reason audit "
            "breadcrumb when present."
        ),
    )
    async def get_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        campaign_id: Annotated[
            UUID,
            Field(description="Target Campaign's id."),
        ],
    ) -> CampaignOutput:
        handler = get_handler()
        campaign = await handler(
            GetCampaign(campaign_id=campaign_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if campaign is None:
            msg = f"Campaign {campaign_id} not found"
            raise ValueError(msg)
        return CampaignOutput(
            id=campaign.id,
            name=campaign.name.value,
            intent=campaign.intent,
            lead_actor_id=campaign.lead_actor_id,
            subject_id=campaign.subject_id,
            description=(campaign.description.value if campaign.description is not None else None),
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
