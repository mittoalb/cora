"""MCP tool for the `version_capability` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.observability import current_correlation_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.capability import (
    CAPABILITY_DESCRIPTION_MAX_LENGTH,
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.version_capability.command import VersionCapability
from cora.recipe.features.version_capability.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_capability` tool on the given MCP server."""

    @mcp.tool(
        name="version_capability",
        description=(
            "Issue a new version label + replacement declarative contract "
            "for an existing Capability. Accepts both Defined and Versioned "
            "source states (subsequent revisions allowed). Deprecated "
            "Capabilities cannot be re-versioned. A new version IS a new "
            "declaration; the supplied required_affordances + executor_shapes "
            "+ description + parameter_schema REPLACE the prior wholesale."
        ),
    )
    async def version_capability_tool(  # pyright: ignore[reportUnusedFunction]
        capability_id: Annotated[
            UUID,
            Field(description="Target Capability's id."),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAPABILITY_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
        required_affordances: Annotated[
            list[Affordance],
            Field(description="Replacement required_affordances for the new version."),
        ],
        executor_shapes: Annotated[
            list[ExecutorShape],
            Field(
                description=(
                    "Replacement executor_shapes for the new version. Required non-empty."
                ),
            ),
        ],
        description: Annotated[
            str | None,
            Field(
                default=None,
                max_length=CAPABILITY_DESCRIPTION_MAX_LENGTH,
                description="Optional human description (0-2000 chars).",
            ),
        ] = None,
        parameter_schema: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Optional declarative JSON Schema (constrained subset). "
                    "Replaces the prior schema wholesale."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            VersionCapability(
                capability_id=capability_id,
                version_tag=version_tag,
                description=description,
                required_affordances=frozenset(required_affordances),
                executor_shapes=frozenset(executor_shapes),
                parameter_schema=parameter_schema,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
