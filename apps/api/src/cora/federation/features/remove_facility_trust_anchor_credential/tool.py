"""MCP tool for the `remove_facility_trust_anchor_credential` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirror of the add tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.features.remove_facility_trust_anchor_credential.command import (
    RemoveFacilityTrustAnchorCredential,
)
from cora.federation.features.remove_facility_trust_anchor_credential.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RemoveFacilityTrustAnchorCredentialOutput(BaseModel):
    """Structured output of the `remove_facility_trust_anchor_credential` MCP tool."""

    facility_id: UUID
    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_facility_trust_anchor_credential` tool on the given MCP server."""

    @mcp.tool(
        name="remove_facility_trust_anchor_credential",
        description=(
            "Unbind a Credential from a Facility's trust-anchor set. "
            "Strict-not-idempotent: re-removing raises. Only Active facilities "
            "accept trust-anchor mutations (Decommissioned facilities reject "
            "all mutations). Once removed, the Seal decider will reject this "
            "credential id as a valid signing key for initialize_seal and "
            "rotate_seal_online_key on this Facility. Optional reason flows "
            "to the event payload for audit-log breadcrumb."
        ),
    )
    async def remove_facility_trust_anchor_credential_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_id: Annotated[
            UUID,
            Field(description="Target facility's id."),
        ],
        credential_id: Annotated[
            UUID,
            Field(description="Credential id to remove from the trust-anchor set."),
        ],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional free-text operator intent for the removal. "
                    "Flows onto the FacilityTrustAnchorCredentialRemoved event "
                    "payload."
                ),
            ),
        ] = None,
    ) -> RemoveFacilityTrustAnchorCredentialOutput:
        handler = get_handler()
        await handler(
            RemoveFacilityTrustAnchorCredential(
                facility_id=FacilityId(facility_id),
                credential_id=CredentialId(credential_id),
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RemoveFacilityTrustAnchorCredentialOutput(
            facility_id=facility_id,
            credential_id=credential_id,
        )
