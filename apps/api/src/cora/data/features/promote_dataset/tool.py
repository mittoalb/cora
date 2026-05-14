"""MCP tool for the `promote_dataset` slice (Phase 7e)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.data._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.data.aggregates.dataset import DATASET_PROMOTION_REASON_MAX_LENGTH
from cora.data.features.promote_dataset.command import PromoteDataset
from cora.data.features.promote_dataset.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `promote_dataset` tool on the given MCP server."""

    @mcp.tool(
        name="promote_dataset",
        description=(
            "Promote a Dataset from Trial to Production intent. Use when "
            "this Dataset is the publication-grade keeper (cited in a paper, "
            "deposited in an archive, etc.). Reason is captured in the audit "
            "log immutably. Strict guards: cannot promote a Discarded dataset; "
            "cannot promote when producing Run did not Complete; cannot "
            "promote when any derived_from Dataset is still Trial. "
            "Strict-not-idempotent: re-promoting raises."
        ),
    )
    async def promote_dataset_tool(  # pyright: ignore[reportUnusedFunction]
        dataset_id: Annotated[
            UUID,
            Field(description="Target dataset's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_PROMOTION_REASON_MAX_LENGTH,
                description="Free-form reason for the promotion (1-500 chars after trimming).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            PromoteDataset(dataset_id=dataset_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
