"""MCP tool for the `promote_caution_proposal` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class PromoteCautionProposalOutput(BaseModel):
    """Structured output of the `promote_caution_proposal` MCP tool."""

    decision_id: UUID
    caution_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `promote_caution_proposal` tool on the FastMCP server."""

    @mcp.tool(
        name="promote_caution_proposal",
        description=(
            "Promote a CautionProposal Decision (authored by CautionDrafter) "
            "into a real Caution via Caution BC's register_caution or "
            "supersede_caution slice. Operator-triggered curation gate; "
            "Decision-mediated workflow per the unanimous propose-via-"
            "Decision verdict. Returns the new caution_id."
        ),
    )
    async def promote_caution_proposal_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        decision_id: Annotated[UUID, Field(description="Target CautionProposal Decision id.")],
    ) -> PromoteCautionProposalOutput:
        handler = get_handler()
        caution_id = await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return PromoteCautionProposalOutput(
            decision_id=decision_id,
            caution_id=caution_id,
        )
