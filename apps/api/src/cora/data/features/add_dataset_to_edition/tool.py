"""MCP tool for the `add_dataset_to_edition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.features.add_dataset_to_edition.command import AddDatasetToEdition
from cora.data.features.add_dataset_to_edition.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AddDatasetToEditionOutput(BaseModel):
    """Structured output for the `add_dataset_to_edition` MCP tool."""

    edition_id: UUID = Field(description="The Edition the Dataset was added to.")
    dataset_id: UUID = Field(description="The Dataset added to the Edition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_dataset_to_edition` tool."""

    @mcp.tool(
        name="add_dataset_to_edition",
        description=(
            "Add an existing Dataset to a Registered Edition. The Edition "
            "must be in Registered state; the Dataset must not be "
            "Discarded and must not already be a member."
        ),
    )
    async def add_dataset_to_edition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        edition_id: Annotated[UUID, Field(description="Edition identifier.")],
        dataset_id: Annotated[UUID, Field(description="Dataset identifier.")],
    ) -> AddDatasetToEditionOutput:
        handler = get_handler()
        await handler(
            AddDatasetToEdition(edition_id=edition_id, dataset_id=dataset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AddDatasetToEditionOutput(edition_id=edition_id, dataset_id=dataset_id)
