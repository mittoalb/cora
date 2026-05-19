"""MCP tool for the `amend_clearance` slice.

Mirrors `register_clearance`'s MCP tool surface for the child fields,
adding `parent_clearance_id` as the cross-aggregate anchor.

The discriminated-union `bindings` / `declarations` arguments are
accepted as JSON dicts whose `kind` discriminator selects the
variant; the tool reuses `register_clearance`'s DTO->domain converters
to keep the wire shape consistent between the two slices.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, TypeAdapter

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.safety._clearance_dtos import (
    BindingDTO,
    HazardDeclarationDTO,
    binding_from_dto,
    declaration_from_dto,
)
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    ClearanceKind,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.features.amend_clearance.command import AmendClearance
from cora.safety.features.amend_clearance.handler import IdempotentHandler

_BINDINGS_ADAPTER = TypeAdapter(list[BindingDTO])
_DECLARATIONS_ADAPTER = TypeAdapter(list[HazardDeclarationDTO])


class AmendClearanceOutput(BaseModel):
    """Structured output of the `amend_clearance` MCP tool."""

    clearance_id: UUID = Field(..., description="The new child clearance's id.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `amend_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="amend_clearance",
        description=(
            "Amend an Active clearance with a new child (atomic: parent "
            "Active -> Superseded, child registered in Defined). Returns the "
            "new child clearance_id. Single-source: requires parent to be "
            "'Active'. The two-stream write is atomic via "
            "EventStore.append_streams (both commit or neither)."
        ),
    )
    async def amend_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        parent_clearance_id: Annotated[UUID, Field(description="Parent clearance's id.")],
        kind: Annotated[ClearanceKind, Field(description="Child form-type.")],
        facility_asset_id: Annotated[
            UUID,
            Field(description="Child's facility Asset.Level.Site reference."),
        ],
        title: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_TITLE_MAX_LENGTH,
                description="Child's operator-readable title.",
            ),
        ],
        bindings: Annotated[
            list[dict[str, Any]],
            Field(
                min_length=1,
                description=(
                    "Child's bindings: list of {kind, id} or {kind: 'External', scheme, id}."
                ),
            ),
        ],
        declarations: Annotated[
            list[dict[str, Any]] | None,
            Field(default=None, description="Child's hazard declarations; empty allowed."),
        ] = None,
        risk_band: Annotated[
            RiskBand | None,
            Field(default=None, description="Optional triage band."),
        ] = None,
        external_id: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
                description="Optional facility-minted regulatory ID.",
            ),
        ] = None,
        valid_from: Annotated[
            datetime | None,
            Field(default=None, description="Child's effective-from timestamp."),
        ] = None,
        valid_until: Annotated[
            datetime | None,
            Field(default=None, description="Child's effective-until timestamp."),
        ] = None,
    ) -> AmendClearanceOutput:
        handler = get_handler()
        # TODO(MCP-auth): when MCP principal extraction lands (SEP-986),
        # swap SYSTEM_PRINCIPAL_ID for the real authenticated principal.

        # Re-validate the polymorphic dict args via the shared DTO adapter so
        # MCP-issued amend calls get the same kind-discriminator + length
        # checks as REST-issued calls.
        parsed_bindings = _BINDINGS_ADAPTER.validate_python(bindings)
        parsed_declarations = _DECLARATIONS_ADAPTER.validate_python(declarations or [])

        child_clearance_id = await handler(
            AmendClearance(
                parent_clearance_id=parent_clearance_id,
                kind=kind,
                facility_asset_id=facility_asset_id,
                title=title,
                bindings=frozenset(binding_from_dto(b) for b in parsed_bindings),
                declarations=frozenset(declaration_from_dto(d) for d in parsed_declarations),
                risk_band=risk_band,
                external_id=external_id,
                valid_from=valid_from,
                valid_until=valid_until,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AmendClearanceOutput(clearance_id=child_clearance_id)
