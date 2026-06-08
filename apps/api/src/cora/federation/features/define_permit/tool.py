"""MCP tool for the `define_permit` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. The `terms` argument is a discriminated
Pydantic model (`kind = "Outbound" | "Inbound"`) mirroring the REST
wire shape.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    InboundTerms,
    OnwardActionScope,
    OutboundTerms,
    ReadScope,
    ReceiptKind,
    ScopeRef,
)
from cora.federation.features.define_permit.command import DefinePermit
from cora.federation.features.define_permit.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class _ScopeRefInput(BaseModel):
    """JSON sub-input for a `ScopeRef`."""

    kind: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    qualifier: str | None = None


class _OutboundTermsInput(BaseModel):
    """JSON sub-input for `OutboundTerms`."""

    kind: Literal["Outbound"]
    scopes: list[_ScopeRefInput] = Field(..., min_length=1)
    read_scope: ReadScope
    onward_action_scope: OnwardActionScope


class _InboundTermsInput(BaseModel):
    """JSON sub-input for `InboundTerms`."""

    kind: Literal["Inbound"]
    inbound_allowed_artifact_kinds: list[str] = Field(..., min_length=1)
    accepted_canonicalization_versions: list[str] | None = None
    required_receipt_kinds: list[ReceiptKind] = Field(default_factory=list[ReceiptKind])
    publisher_grant_correlation_handle: str | None = None


_TermsInput = Annotated[
    _OutboundTermsInput | _InboundTermsInput,
    Field(discriminator="kind"),
]


class DefinePermitOutput(BaseModel):
    """Structured output of the `define_permit` MCP tool."""

    permit_id: UUID


def _build_terms(body: _TermsInput) -> OutboundTerms | InboundTerms:
    if isinstance(body, _OutboundTermsInput):
        return OutboundTerms(
            scopes=frozenset(
                ScopeRef(kind=s.kind, name=s.name, qualifier=s.qualifier) for s in body.scopes
            ),
            read_scope=body.read_scope,
            onward_action_scope=body.onward_action_scope,
        )
    if body.accepted_canonicalization_versions is None:
        return InboundTerms(
            inbound_allowed_artifact_kinds=frozenset(body.inbound_allowed_artifact_kinds),
            required_receipt_kinds=frozenset(body.required_receipt_kinds),
            publisher_grant_correlation_handle=body.publisher_grant_correlation_handle,
        )
    return InboundTerms(
        inbound_allowed_artifact_kinds=frozenset(body.inbound_allowed_artifact_kinds),
        accepted_canonicalization_versions=frozenset(body.accepted_canonicalization_versions),
        required_receipt_kinds=frozenset(body.required_receipt_kinds),
        publisher_grant_correlation_handle=body.publisher_grant_correlation_handle,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_permit` tool on the given MCP server."""

    @mcp.tool(
        name="define_permit",
        description=(
            "Define a new federation Permit (genesis; lands in Defined). "
            "Atomically emits a DecisionRegistered audit on the Decision "
            "stream. Required: peer_facility_code, direction, "
            "allowed_credential_ids, allowed_payload_types, "
            "allowed_artifact_kinds, abi_tier_floor, expires_at, terms. "
            "`terms.kind` discriminates Outbound vs Inbound and must match "
            "`direction`."
        ),
    )
    async def define_permit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        peer_facility_code: Annotated[
            str,
            Field(min_length=1, description="Peer facility code (FacilityCode)."),
        ],
        direction: Annotated[
            Direction,
            Field(description="Permit direction (must match terms.kind)."),
        ],
        allowed_credential_ids: Annotated[
            list[UUID],
            Field(min_length=1, description="Credential ids permitted under this permit."),
        ],
        allowed_payload_types: Annotated[
            list[str],
            Field(min_length=1, description="Payload-type strings honored under this permit."),
        ],
        allowed_artifact_kinds: Annotated[
            list[str],
            Field(min_length=1, description="Artifact-kind strings honored under this permit."),
        ],
        abi_tier_floor: Annotated[
            AbiTier,
            Field(description="Lowest ABI tier the permit honors."),
        ],
        expires_at: Annotated[
            datetime,
            Field(description="Contractual upper bound; must lie strictly after now."),
        ],
        terms: Annotated[
            _TermsInput,
            Field(description="Direction-specific contractual fields (discriminated by `kind`)."),
        ],
    ) -> DefinePermitOutput:
        handler = get_handler()
        permit_id = await handler(
            DefinePermit(
                peer_facility_code=peer_facility_code,
                direction=direction,
                allowed_credential_ids=frozenset(allowed_credential_ids),
                allowed_payload_types=frozenset(allowed_payload_types),
                allowed_artifact_kinds=frozenset(allowed_artifact_kinds),
                abi_tier_floor=abi_tier_floor,
                expires_at=expires_at,
                terms=_build_terms(terms),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefinePermitOutput(permit_id=permit_id)
