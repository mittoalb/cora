"""MCP tool for the `remove_dataset_from_edition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.features.remove_dataset_from_edition.command import (
    RemoveDatasetFromEdition,
)
from cora.data.features.remove_dataset_from_edition.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RemoveDatasetFromEditionOutput(BaseModel):
    edition_id: UUID = Field(description="The Edition the Dataset was removed from.")
    dataset_id: UUID = Field(description="The Dataset removed from the Edition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_dataset_from_edition` tool."""

    @mcp.tool(
        name="remove_dataset_from_edition",
        description=(
            "Remove a Dataset from a Registered Edition. Strict-not-"
            "idempotent: not-member raises; removing the last Dataset "
            "is rejected."
        ),
    )
    async def remove_dataset_from_edition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        edition_id: Annotated[UUID, Field(description="Edition identifier.")],
        dataset_id: Annotated[UUID, Field(description="Dataset identifier.")],
    ) -> RemoveDatasetFromEditionOutput:
        handler = get_handler()
        await handler(
            RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=dataset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RemoveDatasetFromEditionOutput(edition_id=edition_id, dataset_id=dataset_id)
