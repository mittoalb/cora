"""MCP tool for the `get_seal` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.seal import Seal, SealStatus
from cora.federation.features.get_seal.handler import Handler
from cora.federation.features.get_seal.query import GetSeal
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class GetSealOutput(BaseModel):
    """Structured output of the `get_seal` MCP tool.

    `initialized_at` and `initialized_by` are sourced from aggregate
    state (folded from the genesis envelope per the fold-symmetry
    Path C reversal); `last_signed_at` and `last_signed_by` remain
    projection-sourced and nullable when the projection lags or the
    deps lack a pool (in-memory test mode). Mirrors the REST
    `SealResponse` shape.
    """

    facility_code: str
    online_credential_id: UUID
    offline_credential_id: UUID
    current_head_hash: str | None
    current_sequence_number: int
    initialized_by: UUID
    initialized_at: datetime
    status: SealStatus
    last_signed_at: datetime | None = None
    last_signed_by: UUID | None = None


def _output_from_view(
    seal: Seal,
    last_signed_at: datetime | None,
    last_signed_by: UUID | None,
) -> GetSealOutput:
    return GetSealOutput(
        facility_code=seal.facility_code.value,
        online_credential_id=seal.online_credential_id,
        offline_credential_id=seal.offline_credential_id,
        current_head_hash=seal.current_head_hash,
        current_sequence_number=seal.current_sequence_number,
        initialized_by=seal.initialized_by,
        initialized_at=seal.initialized_at,
        status=seal.status,
        last_signed_at=last_signed_at,
        last_signed_by=last_signed_by,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_seal` tool on the given MCP server."""

    @mcp.tool(
        name="get_seal",
        description=(
            "Read the per-facility Seal singleton: key refs (online + "
            "offline), current head hash and sequence number, FSM "
            "status, and lifecycle timestamps. Returns null when no "
            "Seal exists for the given facility."
        ),
    )
    async def get_seal_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_code: Annotated[
            str,
            Field(
                description="Target facility's cross-deployment convergent code.",
                min_length=1,
            ),
        ],
    ) -> GetSealOutput | None:
        handler = get_handler()
        view = await handler(
            GetSeal(facility_code=facility_code),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            return None
        return _output_from_view(
            view.seal,
            view.timestamps.last_signed_at if view.timestamps is not None else None,
            view.timestamps.last_signed_by if view.timestamps is not None else None,
        )
