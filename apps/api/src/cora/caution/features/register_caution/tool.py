"""MCP tool for the `register_caution` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction
and use `SYSTEM_PRINCIPAL_ID` directly until the MCP auth-flow
phase lands.

The polymorphic `target` argument is accepted as a JSON dict whose
`kind` discriminator selects the variant; the tool reuses the shared
`TargetDTO` from `cora.caution._caution_dtos` (via a TypeAdapter) so
MCP-issued register calls get the same discriminator validation as
REST-issued calls.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, TypeAdapter

from cora.caution._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.caution._caution_dtos import TargetDTO, target_from_dto
from cora.caution.aggregates.caution import (
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution.command import RegisterCaution
from cora.caution.features.register_caution.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id

_TARGET_ADAPTER: TypeAdapter[TargetDTO] = TypeAdapter(TargetDTO)


class RegisterCautionOutput(BaseModel):
    """Structured output of the `register_caution` MCP tool."""

    caution_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_caution` tool on the given MCP server."""

    @mcp.tool(
        name="register_caution",
        description=(
            "Register a new operator-authored caution (tribal-knowledge note) "
            "against an Asset or a Procedure. Lands in 'Active' status. "
            "Workaround is REQUIRED. Closed category vocabulary, ANSI Z535 "
            "severity ladder (Notice/Caution/Warning; no Danger tier)."
        ),
    )
    async def register_caution_tool(  # pyright: ignore[reportUnusedFunction]
        target: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Target dict: `{kind: 'Asset', id: <uuid>}` or "
                    "`{kind: 'Procedure', id: <uuid>}`."
                ),
            ),
        ],
        category: Annotated[
            CautionCategory,
            Field(description="Closed category enum."),
        ],
        severity: Annotated[
            CautionSeverity,
            Field(description="Severity (Notice / Caution / Warning)."),
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
            Field(
                default=None,
                description="Optional free-form tags; each 1-50 chars.",
            ),
        ] = None,
        expires_at: Annotated[
            datetime | None,
            Field(default=None, description="Optional auto-retire hint."),
        ] = None,
        propagate_to_children: Annotated[
            bool,
            Field(default=False, description="Asset-hierarchy inheritance opt-in."),
        ] = False,
    ) -> RegisterCautionOutput:
        handler = get_handler()
        parsed_target = _TARGET_ADAPTER.validate_python(target)
        caution_id = await handler(
            RegisterCaution(
                target=target_from_dto(parsed_target),
                category=category,
                severity=severity,
                text=text,
                workaround=workaround,
                tags=frozenset(tags or []),
                expires_at=expires_at,
                propagate_to_children=propagate_to_children,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RegisterCautionOutput(caution_id=caution_id)
