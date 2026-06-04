"""MCP tool for the `list_fixtures` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.features.list_fixtures.handler import Handler
from cora.equipment.features.list_fixtures.query import ListFixtures
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class FixtureSummaryRow(BaseModel):
    fixture_id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    binding_count: int
    override_count: int
    created_at: datetime


class FixtureListOutput(BaseModel):
    """Structured output of the `list_fixtures` MCP tool."""

    items: list[FixtureSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_fixtures` tool on the given MCP server."""

    @mcp.tool(
        name="list_fixtures",
        description=(
            "Cursor-paginated list of Fixtures (summary-only). Three "
            "optional, combinable filters: assembly_id (Fixtures of a "
            "specific blueprint), surface_id (Fixtures on a specific "
            "Trust Surface / beamline), assembly_content_hash "
            "(Fixtures sharing a structural fingerprint across "
            "facilities). For full slot_asset_bindings + "
            "parameter_overrides, call get_fixture per id."
        ),
    )
    async def list_fixtures_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        assembly_id: Annotated[
            UUID | None,
            Field(description="Only Fixtures of this Assembly blueprint."),
        ] = None,
        surface_id: Annotated[
            UUID | None,
            Field(description="Only Fixtures registered on this Trust Surface."),
        ] = None,
        assembly_content_hash: Annotated[
            str | None,
            Field(description="Only Fixtures whose snapshot matches this content_hash."),
        ] = None,
    ) -> FixtureListOutput:
        handler = get_handler()
        page = await handler(
            ListFixtures(
                cursor=cursor,
                limit=limit,
                assembly_id=assembly_id,
                surface_id=surface_id,
                assembly_content_hash=assembly_content_hash,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return FixtureListOutput(
            items=[
                FixtureSummaryRow(
                    fixture_id=item.fixture_id,
                    assembly_id=item.assembly_id,
                    assembly_content_hash=item.assembly_content_hash,
                    surface_id=item.surface_id,
                    binding_count=item.binding_count,
                    override_count=item.override_count,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
