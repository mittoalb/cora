"""MCP tool for the `seal_edition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.aggregates.edition import (
    EDITION_LICENSE_MAX_LENGTH,
)
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.seal_edition.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SealEditionOutput(BaseModel):
    """Structured output of the `seal_edition` MCP tool."""

    edition_id: UUID = Field(description="Identifier of the sealed Edition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `seal_edition` tool on the given MCP server."""

    @mcp.tool(
        name="seal_edition",
        description=(
            "Seal a Registered Edition: snapshot member Dataset ids, "
            "resolve publisher Facility, compute the canonical content "
            "hash via the per-kind serializer, and transition to Sealed."
        ),
    )
    async def seal_edition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        edition_id: Annotated[UUID, Field(description="The Edition to seal.")],
        publisher_facility_code: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional publisher Facility code override. Falls back "
                    "to the value supplied at register-time."
                ),
            ),
        ] = None,
        publication_year_override: Annotated[
            int | None,
            Field(
                default=None,
                description=("Optional publication year override."),
            ),
        ] = None,
        license_override: Annotated[
            str | None,
            Field(
                default=None,
                max_length=EDITION_LICENSE_MAX_LENGTH,
                description=("Optional SPDX license identifier override."),
            ),
        ] = None,
    ) -> SealEditionOutput:
        handler = get_handler()
        await handler(
            SealEdition(
                edition_id=edition_id,
                publisher_facility_code=publisher_facility_code,
                publication_year_override=publication_year_override,
                license_override=license_override,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SealEditionOutput(edition_id=edition_id)
