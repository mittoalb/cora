"""MCP tool for the `update_family_settings_schema` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.update_family_settings_schema.command import (
    UpdateFamilySettingsSchema,
)
from cora.equipment.features.update_family_settings_schema.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_family_settings_schema` MCP tool."""

    @mcp.tool(
        name="update_family_settings_schema",
        description=(
            "Set, replace, or clear a Family's settings_schema "
            "(JSON Schema Draft 2020-12, constrained subset). The "
            "schema declares the shape of Asset.settings keys this "
            "Family owns. Pass null for settings_schema to clear "
            "an existing declaration. Phase 5g-a: pre-positions for "
            "the Asset.settings runtime validation hook in 5g-c."
        ),
    )
    async def update_family_settings_schema_tool(  # pyright: ignore[reportUnusedFunction]
        family_id: Annotated[UUID, Field(description="Target capability's id.")],
        settings_schema: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "JSON Schema (Draft 2020-12 subset) or null to clear. "
                    "Required keys when present: $schema "
                    "(https://json-schema.org/draft/2020-12/schema). "
                    "Subset: type, required, properties, enum, minimum, "
                    "maximum, pattern."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateFamilySettingsSchema(
                family_id=family_id,
                settings_schema=settings_schema,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
