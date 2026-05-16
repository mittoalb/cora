"""MCP tool for the `get_caution` query slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. On miss the tool raises ValueError so FastMCP
wraps the response as `isError: true` with a clear diagnostic, same
convention as `get_supply` / `get_clearance`.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.caution._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.caution.aggregates.caution import (
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    serialize_target,
)
from cora.caution.features.get_caution.handler import Handler
from cora.caution.features.get_caution.query import GetCaution
from cora.infrastructure.observability import current_correlation_id


class CautionOutput(BaseModel):
    """Structured output of the `get_caution` MCP tool (on hit)."""

    id: UUID
    target: dict[str, Any]
    category: CautionCategory
    severity: CautionSeverity
    text: str
    workaround: str
    author_actor_id: UUID
    tags: list[str]
    expires_at: datetime | None
    propagate_to_children: bool
    status: CautionStatus
    parent_caution_id: UUID | None = None
    superseded_by_caution_id: UUID | None = None
    retired_reason: CautionRetireReason | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_caution` tool on the given MCP server."""

    @mcp.tool(
        name="get_caution",
        description=(
            "Look up a caution by id. Returns target, classification, body, "
            "author, tags, expires_at, propagation flag, and current FSM "
            "status (Active / Superseded / Retired) plus supersede/retire "
            "metadata when terminal."
        ),
    )
    async def get_caution_tool(  # pyright: ignore[reportUnusedFunction]
        caution_id: Annotated[
            UUID,
            Field(description="Target caution's id."),
        ],
    ) -> CautionOutput:
        handler = get_handler()
        caution = await handler(
            GetCaution(caution_id=caution_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if caution is None:
            msg = f"Caution {caution_id} not found"
            raise ValueError(msg)
        return CautionOutput(
            id=caution.id,
            target=serialize_target(caution.target),
            category=caution.category,
            severity=caution.severity,
            text=caution.text.value,
            workaround=caution.workaround.value,
            author_actor_id=caution.author_actor_id,
            tags=sorted(t.value for t in caution.tags),
            expires_at=caution.expires_at,
            propagate_to_children=caution.propagate_to_children,
            status=caution.status,
            parent_caution_id=caution.parent_caution_id,
            superseded_by_caution_id=caution.superseded_by_caution_id,
            retired_reason=caution.retired_reason,
        )
