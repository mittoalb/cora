"""MCP tool for the `register_edition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.aggregates.edition import (
    EDITION_AFFILIATION_MAX_LENGTH,
    EDITION_CREATORS_MAX,
    EDITION_CREATORS_MIN,
    EDITION_LICENSE_MAX_LENGTH,
    EDITION_TITLE_MAX_LENGTH,
    EditionKind,
)
from cora.data.features.register_edition.command import (
    CreatorEntry,
    RegisterEdition,
)
from cora.data.features.register_edition.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class CreatorMcpInput(BaseModel):
    actor_id: UUID
    affiliation: str | None = Field(
        default=None,
        max_length=EDITION_AFFILIATION_MAX_LENGTH,
    )


class RegisterEditionOutput(BaseModel):
    """Structured output of the `register_edition` MCP tool."""

    edition_id: UUID = Field(description="Identifier of the newly registered Edition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_edition` tool on the given MCP server."""

    @mcp.tool(
        name="register_edition",
        description=(
            "Register a new Edition (citable publication-package over a "
            "set of Datasets). kind is a closed enum (ROCrate, DataCite, "
            "Croissant, OAIS_AIP, OAIS_DIP, NeXus). license / "
            "publisher_facility_code / publication_year are optional at "
            "register-time; license + publisher + year are required at "
            "seal-time for the relevant kinds."
        ),
    )
    async def register_edition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        kind: Annotated[
            EditionKind,
            Field(description="Serialization-target kind (closed enum)."),
        ],
        title: Annotated[
            str,
            Field(min_length=1, max_length=EDITION_TITLE_MAX_LENGTH),
        ],
        dataset_ids: Annotated[
            list[UUID],
            Field(min_length=1, description="Initial member Dataset ids."),
        ],
        creators: Annotated[
            list[CreatorMcpInput],
            Field(
                min_length=EDITION_CREATORS_MIN,
                max_length=EDITION_CREATORS_MAX,
                description="Ordered creators list (order publication-significant).",
            ),
        ],
        license: Annotated[
            str | None,
            Field(default=None, max_length=EDITION_LICENSE_MAX_LENGTH),
        ] = None,
        publication_year: Annotated[
            int | None,
            Field(default=None),
        ] = None,
        publisher_facility_code: Annotated[
            str | None,
            Field(default=None),
        ] = None,
    ) -> RegisterEditionOutput:
        handler = get_handler()
        edition_id = await handler(
            RegisterEdition(
                kind=kind.value,
                title=title,
                dataset_ids=frozenset(dataset_ids),
                creators=tuple(
                    CreatorEntry(actor_id=c.actor_id, affiliation=c.affiliation) for c in creators
                ),
                license=license,
                publication_year=publication_year,
                publisher_facility_code=publisher_facility_code,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterEditionOutput(edition_id=edition_id)
