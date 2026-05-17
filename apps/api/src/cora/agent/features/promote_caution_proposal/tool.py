"""MCP tool for the `promote_caution_proposal` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id


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
            "Decision-mediated workflow per Stage 0 unanimous propose-via-"
            "Decision verdict. Returns the new caution_id."
        ),
    )
    async def promote_caution_proposal_tool(  # pyright: ignore[reportUnusedFunction]
        decision_id: Annotated[UUID, Field(description="Target CautionProposal Decision id.")],
    ) -> PromoteCautionProposalOutput:
        handler = get_handler()
        caution_id = await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return PromoteCautionProposalOutput(
            decision_id=decision_id,
            caution_id=caution_id,
        )
