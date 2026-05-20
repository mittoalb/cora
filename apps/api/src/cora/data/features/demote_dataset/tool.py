"""MCP tool for the `demote_dataset` slice (post-Q4 compensation primitive)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.data._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.data.aggregates.dataset import DATASET_DEMOTION_REASON_MAX_LENGTH
from cora.data.features.demote_dataset.command import DemoteDataset
from cora.data.features.demote_dataset.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `demote_dataset` tool on the given MCP server."""

    @mcp.tool(
        name="demote_dataset",
        description=(
            "Demote a Dataset from Production to Retracted intent (terminal). "
            "Use when an authoritative dataset must be retracted: discovered "
            "calibration error, methodology challenged post-publication, sample "
            "compromised, etc. Reason is captured in the audit log immutably. "
            "Strict guards: cannot demote a Discarded dataset; cannot demote a "
            "Trial dataset (use discard_dataset for Trial cleanup). "
            "Strict-not-idempotent: re-demoting raises. Terminal Intent: no "
            "re-promote from Retracted (register a NEW dataset with derived_from "
            "if you want to re-publish a corrected version)."
        ),
    )
    async def demote_dataset_tool(  # pyright: ignore[reportUnusedFunction]
        dataset_id: Annotated[
            UUID,
            Field(description="Target dataset's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DATASET_DEMOTION_REASON_MAX_LENGTH,
                description="Free-form reason for the demotion (1-500 chars after trimming).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DemoteDataset(dataset_id=dataset_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
