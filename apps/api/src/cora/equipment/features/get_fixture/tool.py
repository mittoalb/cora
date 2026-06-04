"""MCP tool for the `get_fixture` query slice.

Surfaces the same handler the REST route uses. Returns a structured
FixtureOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic; matches the REST 404
behaviour in MCP's error idiom (LLM consumers get a clear "Fixture
not found" message rather than null structuredContent they have to
interpret).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.features.get_fixture.handler import Handler
from cora.equipment.features.get_fixture.query import GetFixture
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SlotAssetBindingOutput(BaseModel):
    """A single (slot_name, asset_id) binding within a Fixture."""

    slot_name: str
    asset_id: UUID


class FixtureOutput(BaseModel):
    """Structured output of the `get_fixture` MCP tool."""

    id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    slot_asset_bindings: list[SlotAssetBindingOutput] = Field(
        default_factory=list[SlotAssetBindingOutput]
    )
    parameter_overrides: dict[str, Any] = Field(default_factory=dict[str, Any])
    registered_at: datetime | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_fixture` tool on the given MCP server."""

    @mcp.tool(
        name="get_fixture",
        description=(
            "Read the current state of an existing Fixture by id. "
            "Returns the full Fixture including slot_asset_bindings "
            "(which Assets are bound to which slots) and "
            "parameter_overrides."
        ),
    )
    async def get_fixture_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        fixture_id: Annotated[
            UUID,
            Field(description="Target Fixture's id."),
        ],
    ) -> FixtureOutput:
        handler = get_handler()
        fixture = await handler(
            GetFixture(fixture_id=fixture_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if fixture is None:
            msg = f"Fixture {fixture_id} not found"
            raise ValueError(msg)
        bindings = sorted(
            (
                SlotAssetBindingOutput(slot_name=b.slot_name, asset_id=b.asset_id)
                for b in fixture.slot_asset_bindings
            ),
            key=lambda b: (b.slot_name, str(b.asset_id)),
        )
        return FixtureOutput(
            id=fixture.id,
            assembly_id=fixture.assembly_id,
            assembly_content_hash=fixture.assembly_content_hash,
            surface_id=fixture.surface_id,
            slot_asset_bindings=bindings,
            parameter_overrides=fixture.parameter_overrides,
            registered_at=fixture.registered_at,
        )
