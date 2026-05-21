"""MCP tool for the `list_policies` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.policy import POLICY_NAME_MAX_LENGTH
from cora.trust.features.list_policies.handler import Handler
from cora.trust.features.list_policies.query import ListPolicies


class PolicySummaryRow(BaseModel):
    policy_id: UUID
    name: str = Field(..., max_length=POLICY_NAME_MAX_LENGTH)
    conduit_id: UUID
    created_at: datetime


class PolicyListOutput(BaseModel):
    """Structured output of the `list_policies` MCP tool."""

    items: list[PolicySummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_policies` tool on the given MCP server."""

    @mcp.tool(
        name="list_policies",
        description=(
            "Cursor-paginated list of Trust policies (authorization "
            "rules attached to a Conduit). Optional `conduit_id` "
            "filter narrows by governed Conduit. Pass `cursor` from "
            "a previous page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_policies_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        conduit_id: Annotated[
            UUID | None,
            Field(description="Optional conduit-scope filter; omit for any conduit."),
        ] = None,
    ) -> PolicyListOutput:
        handler = get_handler()
        page = await handler(
            ListPolicies(cursor=cursor, limit=limit, conduit_id=conduit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return PolicyListOutput(
            items=[
                PolicySummaryRow(
                    policy_id=item.policy_id,
                    name=item.name,
                    conduit_id=item.conduit_id,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
