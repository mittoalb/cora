"""MCP tool for the `get_permit` query slice.

Surfaces the same handler the REST route uses. Returns the full
polymorphic Permit shape with the `terms` field discriminated by
`kind`. Misses raise `PermitNotFoundError`, matching the REST 404
posture (MCP surfaces it as a tool error).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.get_permit.handler import Handler, PermitView
from cora.federation.features.get_permit.query import GetPermit
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class _ScopeRefOutput(BaseModel):
    """Structured-output sub-shape for a `ScopeRef`."""

    kind: str
    name: str
    qualifier: str | None = None


class _OutboundTermsOutput(BaseModel):
    """Structured-output sub-shape for outbound terms."""

    kind: Literal["Outbound"]
    scopes: list[_ScopeRefOutput]
    read_scope: str
    onward_action_scope: str


class _InboundTermsOutput(BaseModel):
    """Structured-output sub-shape for inbound terms."""

    kind: Literal["Inbound"]
    inbound_allowed_artifact_kinds: list[str]
    accepted_canonicalization_versions: list[str]
    required_receipt_kinds: list[str]
    publisher_grant_correlation_handle: str | None = None


_TermsOutput = Annotated[
    _OutboundTermsOutput | _InboundTermsOutput,
    Field(discriminator="kind"),
]


class GetPermitOutput(BaseModel):
    """Structured output of the `get_permit` MCP tool.

    Mirrors the REST `PermitResponse` shape. Lifecycle timestamps are
    projection-sourced per Path C and nullable for transitions that
    have not yet fired.
    """

    id: UUID
    peer_facility_id: str
    direction: str
    allowed_credentials: list[UUID]
    allowed_payload_types: list[str]
    allowed_artifact_kinds: list[str]
    abi_tier_floor: str
    expires_at: datetime
    defined_by_actor_id: UUID
    status: str
    terms: _TermsOutput
    defined_at: datetime
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    resumed_at: datetime | None = None
    revoked_at: datetime | None = None


def _terms_output(view: PermitView) -> _TermsOutput:
    if view.terms_kind == "Outbound":
        scopes = view.scopes or []
        return _OutboundTermsOutput(
            kind="Outbound",
            scopes=[
                _ScopeRefOutput(
                    kind=s["kind"],
                    name=s["name"],
                    qualifier=s.get("qualifier"),
                )
                for s in scopes
            ],
            read_scope=view.read_scope or "",
            onward_action_scope=view.onward_action_scope or "",
        )
    return _InboundTermsOutput(
        kind="Inbound",
        inbound_allowed_artifact_kinds=view.inbound_allowed_artifact_kinds or [],
        accepted_canonicalization_versions=view.accepted_canonicalization_versions or [],
        required_receipt_kinds=view.required_receipt_kinds or [],
        publisher_grant_correlation_handle=view.publisher_grant_correlation_handle,
    )


def _output_from_view(view: PermitView) -> GetPermitOutput:
    return GetPermitOutput(
        id=view.permit_id,
        peer_facility_id=view.peer_facility_id,
        direction=view.direction,
        allowed_credentials=list(view.allowed_credentials),
        allowed_payload_types=list(view.allowed_payload_types),
        allowed_artifact_kinds=list(view.allowed_artifact_kinds),
        abi_tier_floor=view.abi_tier_floor,
        expires_at=view.expires_at,
        defined_by_actor_id=view.defined_by_actor_id,
        status=view.status,
        terms=_terms_output(view),
        defined_at=view.defined_at,
        activated_at=view.activated_at,
        suspended_at=view.suspended_at,
        resumed_at=view.resumed_at,
        revoked_at=view.revoked_at,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_permit` tool on the given MCP server."""

    @mcp.tool(
        name="get_permit",
        description=(
            "Read the current state of an existing federation Permit by "
            "id (identity + direction + per-direction terms + lifecycle "
            "status and timestamps). Raises an error if no Permit matches."
        ),
    )
    async def get_permit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        permit_id: Annotated[
            UUID,
            Field(description="Target permit's id."),
        ],
    ) -> GetPermitOutput:
        handler = get_handler()
        view = await handler(
            GetPermit(permit_id=permit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return _output_from_view(view)
