"""MCP tool for the `register_visit` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.external_ref import ExternalRef
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.visit import VisitType
from cora.trust.features.register_visit.command import RegisterVisit
from cora.trust.features.register_visit.handler import IdempotentHandler


class _ExternalRefInput(BaseModel):
    scheme: str = Field(..., min_length=1, max_length=50)
    id: str = Field(..., min_length=1, max_length=200)


class RegisterVisitOutput(BaseModel):
    """Structured output of the `register_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_visit` tool on the given MCP server."""

    @mcp.tool(
        name="register_visit",
        description=(
            "Register a new Visit (operational envelope) on a Surface under a "
            "Policy. Caller supplies visit_id. Status starts at 'Planned'. "
            "Type is closed: user / commissioning / maintenance / "
            "calibration / staff."
        ),
    )
    async def register_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Caller-supplied UUID.")],
        policy_id: Annotated[
            UUID,
            Field(description="Policy that scopes this visit's authz."),
        ],
        surface_id: Annotated[
            UUID,
            Field(description="Surface this visit binds to."),
        ],
        type: Annotated[
            VisitType,
            Field(description="user / commissioning / maintenance / calibration / staff."),
        ],
        planned_start_at: Annotated[datetime, Field(description="Scheduled start.")],
        planned_end_at: Annotated[
            datetime,
            Field(description="Scheduled end; must be strictly after planned_start_at."),
        ],
        part_of_visit_id: Annotated[
            UUID | None,
            Field(description="Optional self-FK for nested commissioning (Phase delta)."),
        ] = None,
        external_refs: Annotated[
            list[_ExternalRefInput],
            Field(description="Anti-corruption refs to upstream concepts (Phase epsilon)."),
        ] = [],  # noqa: B006  -- MCP requires literal default, frozen via tuple-conversion below
    ) -> RegisterVisitOutput:
        handler = get_handler()
        await handler(
            RegisterVisit(
                visit_id=visit_id,
                policy_id=policy_id,
                surface_id=surface_id,
                type=type,
                planned_start_at=planned_start_at,
                planned_end_at=planned_end_at,
                part_of_visit_id=part_of_visit_id,
                external_refs=frozenset(
                    ExternalRef(scheme=r.scheme, id=r.id) for r in external_refs
                ),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterVisitOutput(visit_id=visit_id)
