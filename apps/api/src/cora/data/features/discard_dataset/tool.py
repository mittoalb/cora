"""MCP tool for the `discard_dataset` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.data._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.data.aggregates.dataset import DATASET_DISCARD_REASON_MAX_LENGTH
from cora.data.features.discard_dataset.command import DiscardDataset
from cora.data.features.discard_dataset.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `discard_dataset` tool on the given MCP server."""

    @mcp.tool(
        name="discard_dataset",
        description=(
            "Discard a Dataset (Registered → Discarded). Use when bytes at "
            "the URI have been deleted from storage and the metadata record "
            "should reflect that. The Data BC does NOT delete the bytes; "
            "that's an out-of-band operator workflow. Re-discarding raises. "
            "Reason is free-form (1-500 chars), captured verbatim for audit."
        ),
    )
    async def discard_dataset_tool(  # pyright: ignore[reportUnusedFunction]
        dataset_id: Annotated[
            UUID,
            Field(description="Target dataset's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_DISCARD_REASON_MAX_LENGTH,
                description="Free-form reason for the discard (1-500 chars after trimming).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DiscardDataset(dataset_id=dataset_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
