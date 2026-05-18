"""MCP tool for the `version_family` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.family import FAMILY_VERSION_TAG_MAX_LENGTH, Affordance
from cora.equipment.features.version_family.command import VersionFamily
from cora.equipment.features.version_family.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_family` tool on the given MCP server."""

    @mcp.tool(
        name="version_family",
        description=(
            "Issue a new version label + replacement affordance set for "
            "an existing Family. Accepts both Defined and Versioned "
            "source states (subsequent revisions allowed). Deprecated "
            "Families cannot be re-versioned. A new version IS a new "
            "declaration; the supplied affordance set REPLACES the prior."
        ),
    )
    async def version_family_tool(  # pyright: ignore[reportUnusedFunction]
        family_id: Annotated[
            UUID,
            Field(description="Target Family's id."),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=FAMILY_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
        affordances: Annotated[
            list[Affordance],
            Field(
                description=(
                    "Replacement affordance set for the new version. "
                    "Supply `[]` explicitly to clear all affordances."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            VersionFamily(
                family_id=family_id,
                version_tag=version_tag,
                affordances=frozenset(affordances),
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
