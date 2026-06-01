"""MCP tool for the `supersede_caution` slice.

Mirrors `register_caution`'s MCP tool surface for the child fields,
adding `parent_caution_id` as the cross-aggregate anchor.

The polymorphic `target` argument is accepted as a JSON dict whose
`kind` discriminator selects the variant; reuses `register_caution`'s
shared `TargetDTO` to keep the wire shape consistent.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field, TypeAdapter

from cora.caution._caution_dtos import TargetDTO, target_from_dto
from cora.caution.aggregates.caution import (
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.supersede_caution.command import SupersedeCaution
from cora.caution.features.supersede_caution.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id

_TARGET_ADAPTER: TypeAdapter[TargetDTO] = TypeAdapter(TargetDTO)


class SupersedeCautionOutput(BaseModel):
    """Structured output of the `supersede_caution` MCP tool."""

    caution_id: UUID = Field(..., description="The new child caution's id.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `supersede_caution` tool on the given MCP server."""

    @mcp.tool(
        name="supersede_caution",
        description=(
            "Supersede an Active caution with a new child (atomic: parent "
            "Active -> Superseded, child registered in Active). Returns the "
            "new child caution_id. Single-source: requires parent to be "
            "'Active'. Child target MUST match parent's. The two-stream "
            "write is atomic via EventStore.append_streams."
        ),
    )
    async def supersede_caution_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        parent_caution_id: Annotated[UUID, Field(description="Parent caution's id.")],
        target: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Target dict: `{kind: 'Asset', id: <uuid>}` or "
                    "`{kind: 'Procedure', id: <uuid>}`. MUST match parent's target."
                ),
            ),
        ],
        category: Annotated[
            CautionCategory,
            Field(
                description=(
                    "Closed caution category from a fixed vocabulary "
                    "(Wear, Calibration, Wiring, OperationalWindow, "
                    "InterlockQuirk, ProcedureGotcha)."
                ),
            ),
        ],
        severity: Annotated[
            CautionSeverity,
            Field(
                description=(
                    "Caution severity on the ANSI Z535 ladder "
                    "(Notice, Caution, Warning); no Danger tier."
                ),
            ),
        ],
        text: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAUTION_TEXT_MAX_LENGTH,
                description="Free-form caution body.",
            ),
        ],
        workaround: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAUTION_WORKAROUND_MAX_LENGTH,
                description="REQUIRED. What does the operator do about it?",
            ),
        ],
        tags: Annotated[
            list[str] | None,
            Field(default=None, description="Optional free-form tags."),
        ] = None,
        expires_at: Annotated[
            datetime | None,
            Field(default=None, description="Optional auto-retire hint."),
        ] = None,
        propagate_to_children: Annotated[
            bool,
            Field(default=False, description="Asset-hierarchy inheritance opt-in."),
        ] = False,
    ) -> SupersedeCautionOutput:
        handler = get_handler()
        parsed_target = _TARGET_ADAPTER.validate_python(target)
        child_caution_id = await handler(
            SupersedeCaution(
                parent_caution_id=parent_caution_id,
                target=target_from_dto(parsed_target),
                category=category,
                severity=severity,
                text=text,
                workaround=workaround,
                tags=frozenset(tags or []),
                expires_at=expires_at,
                propagate_to_children=propagate_to_children,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SupersedeCautionOutput(caution_id=child_caution_id)
