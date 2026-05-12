"""MCP tool for the `list_capabilities` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.capability import (
    CAPABILITY_NAME_MAX_LENGTH,
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
)
from cora.equipment.features.list_capabilities.handler import Handler
from cora.equipment.features.list_capabilities.query import (
    CapabilityStatusFilter,
    ListCapabilities,
)
from cora.infrastructure.observability import current_correlation_id


class CapabilitySummaryRow(BaseModel):
    capability_id: UUID
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: CapabilityStatusFilter
    version_tag: str | None = Field(default=None, max_length=CAPABILITY_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class CapabilityListOutput(BaseModel):
    """Structured output of the `list_capabilities` MCP tool."""

    items: list[CapabilitySummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_capabilities` tool on the given MCP server."""

    @mcp.tool(
        name="list_capabilities",
        description=(
            "Cursor-paginated list of capabilities. Optional `status` "
            "filter accepts: Defined, Versioned, Deprecated. Pass "
            "`cursor` from a previous page's `next_cursor` to fetch "
            "the next page."
        ),
    )
    async def list_capabilities_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            CapabilityStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> CapabilityListOutput:
        handler = get_handler()
        page = await handler(
            ListCapabilities(cursor=cursor, limit=limit, status=status),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return CapabilityListOutput(
            items=[
                CapabilitySummaryRow(
                    capability_id=item.capability_id,
                    name=item.name,
                    status=item.status,  # type: ignore[arg-type]
                    version_tag=item.version_tag,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
