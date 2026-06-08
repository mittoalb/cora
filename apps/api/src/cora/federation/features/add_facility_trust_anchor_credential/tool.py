"""MCP tool for the `add_facility_trust_anchor_credential` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.features.add_facility_trust_anchor_credential.command import (
    AddFacilityTrustAnchorCredential,
)
from cora.federation.features.add_facility_trust_anchor_credential.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AddFacilityTrustAnchorCredentialOutput(BaseModel):
    """Structured output of the `add_facility_trust_anchor_credential` MCP tool."""

    facility_id: UUID
    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_facility_trust_anchor_credential` tool on the given MCP server."""

    @mcp.tool(
        name="add_facility_trust_anchor_credential",
        description=(
            "Bind a Credential as a trust anchor on a Facility. Strict-not-"
            "idempotent: re-adding raises. Only Active, kind=Site facilities "
            "accept trust-anchor mutations (Area facilities inherit the "
            "parent Site's trust posture; Decommissioned facilities reject "
            "all mutations). Once bound, the Seal decider accepts this "
            "credential id as a valid online or offline signing key for "
            "initialize_seal and rotate_seal_online_key on this Facility."
        ),
    )
    async def add_facility_trust_anchor_credential_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_id: Annotated[
            UUID,
            Field(description="Target facility's id."),
        ],
        credential_id: Annotated[
            UUID,
            Field(description="Credential id to add to the trust-anchor set."),
        ],
    ) -> AddFacilityTrustAnchorCredentialOutput:
        handler = get_handler()
        await handler(
            AddFacilityTrustAnchorCredential(
                facility_id=FacilityId(facility_id),
                credential_id=CredentialId(credential_id),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AddFacilityTrustAnchorCredentialOutput(
            facility_id=facility_id,
            credential_id=credential_id,
        )
