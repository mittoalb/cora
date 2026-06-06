"""MCP tool for the `list_cautions` query slice.

Mirrors the REST route's behavior including the `status=[Active]`
default and the `min_severity` ladder convenience. The defaults
MUST match the REST surface; agents and operators see the same
filtered view so a bug surfaced in one client surfaces in the other.

User-facing translation (status default, status='all' sentinel,
severity vs min_severity exclusivity) lives here at the tool
boundary; the application handler sees only canonical list-typed
filters per the `cora.infrastructure.list_query` growth-rule
discipline.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.caution._caution_dtos import (
    TargetAssetDTO,
    TargetDTO,
    TargetProcedureDTO,
)
from cora.caution.aggregates.caution import (
    CAUTION_TAG_MAX_LENGTH,
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
)
from cora.caution.features.list_cautions.handler import Handler
from cora.caution.features.list_cautions.query import (
    CautionCategoryFilter,
    CautionSeverityFilter,
    CautionStatusFilter,
    CautionTargetKindFilter,
    ListCautions,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id

# Tool-surface type for status, matching the route's `_RouteStatusParam`
# semantics: real values plus the 'all' sentinel.
_ToolStatusParam = Literal["Active", "Superseded", "Retired", "all"]

# Same ladder as the route. Kept duplicated rather than imported from
# route.py to avoid coupling tool layer to route layer (both depend on
# the same domain ladder, neither depends on the other).
_SEVERITY_LADDER: dict[CautionSeverityFilter, list[CautionSeverityFilter]] = {
    "Notice": ["Notice", "Caution", "Warning"],
    "Caution": ["Caution", "Warning"],
    "Warning": ["Warning"],
}


class _ListCautionsInputError(ValueError):
    """Raised when caller passes conflicting filter inputs (severity +
    min_severity together, or 'all' mixed with explicit status values).

    MCP runtime surfaces ValueError as a tool error, parallel to the
    REST route's HTTPException(422).
    """


def _resolve_severities(
    severity: list[CautionSeverityFilter] | None,
    min_severity: CautionSeverityFilter | None,
) -> list[CautionSeverityFilter] | None:
    """Mirror of `route._resolve_severities`. See route docstring."""
    has_severity = severity is not None and len(severity) > 0
    has_min = min_severity is not None
    if has_severity and has_min:
        raise _ListCautionsInputError(
            "Pass either `severity` (one or more exact values) or "
            "`min_severity` (Notice<Caution<Warning ladder), not both."
        )
    if has_severity:
        return severity
    if has_min:
        assert min_severity is not None
        return list(_SEVERITY_LADDER[min_severity])
    return None


def _resolve_statuses(
    status_params: list[_ToolStatusParam] | None,
) -> list[CautionStatusFilter] | None:
    """Mirror of `route._resolve_statuses`. See route docstring.

    Default (None or empty) -> ['Active'], same as the REST route.
    """
    if status_params is None or len(status_params) == 0:
        return ["Active"]
    has_all = "all" in status_params
    if has_all and len(status_params) > 1:
        raise _ListCautionsInputError(
            "Pass either `status=all` (disable filter) or one or "
            "more explicit status values, not both."
        )
    if has_all:
        return None
    return [v for v in status_params if v != "all"]


def _target_dto_from_row(target_kind: str, target_id: UUID) -> TargetDTO:
    if target_kind == "Asset":
        return TargetAssetDTO(kind="Asset", id=target_id)
    return TargetProcedureDTO(kind="Procedure", id=target_id)


class CautionSummaryRow(BaseModel):
    caution_id: UUID
    target: TargetDTO
    category: CautionCategory
    severity: CautionSeverity
    text: str = Field(..., max_length=CAUTION_TEXT_MAX_LENGTH)
    workaround: str = Field(..., max_length=CAUTION_WORKAROUND_MAX_LENGTH)
    author_actor_id: UUID
    tags: list[str] = Field(default_factory=list[str])
    expires_at: datetime | None = None
    propagate_to_children: bool = False
    status: CautionStatus
    parent_id: UUID | None = None
    superseded_by_caution_id: UUID | None = None
    retired_reason: CautionRetireReason | None = None
    registered_at: datetime
    last_status_changed_at: datetime | None = None


class CautionListOutput(BaseModel):
    """Structured output of the `list_cautions` MCP tool."""

    items: list[CautionSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_cautions` tool on the given MCP server."""

    @mcp.tool(
        name="list_cautions",
        description=(
            "Cursor-paginated list of cautions. Optional filters: "
            "`target_kind` (Asset / Procedure), `target_id`, `category` "
            "(one of the 6 CautionCategory values), `severity` (one or "
            "more exact values), `min_severity` (Notice<Caution<Warning "
            "ladder; cannot be combined with severity), `status` (one or "
            "more values; defaults to ['Active']; pass ['all'] to "
            "include every status), `tag` (exact match in the tags "
            "array), `author_actor_id`. Pass `cursor` from a previous "
            "page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_cautions_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        target_kind: Annotated[
            CautionTargetKindFilter | None,
            Field(description="Optional target-kind filter (Asset / Procedure)."),
        ] = None,
        target_id: Annotated[
            UUID | None,
            Field(description="Optional target-id filter."),
        ] = None,
        category: Annotated[
            CautionCategoryFilter | None,
            Field(description="Optional category filter; omit to list all."),
        ] = None,
        severities: Annotated[
            list[CautionSeverityFilter] | None,
            Field(
                description=(
                    "Optional exact severity filter; multi-value. "
                    "Cannot be combined with `min_severity`."
                ),
            ),
        ] = None,
        min_severity: Annotated[
            CautionSeverityFilter | None,
            Field(
                description=(
                    "Optional severity-threshold filter; expands to the "
                    "matching suffix of the Notice<Caution<Warning "
                    "ladder. Cannot be combined with `severity`."
                ),
            ),
        ] = None,
        statuses: Annotated[
            list[_ToolStatusParam] | None,
            Field(
                description=(
                    "Optional status filter; multi-value; defaults to "
                    "['Active']. Pass ['all'] alone to include every "
                    "status."
                ),
            ),
        ] = None,
        tag: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=CAUTION_TAG_MAX_LENGTH,
                description="Optional tag filter (exact match in the tags array).",
            ),
        ] = None,
        author_actor_id: Annotated[
            UUID | None,
            Field(description="Optional author filter."),
        ] = None,
    ) -> CautionListOutput:
        resolved_severities = _resolve_severities(severities, min_severity)
        resolved_statuses = _resolve_statuses(statuses)
        handler = get_handler()
        page = await handler(
            ListCautions(
                cursor=cursor,
                limit=limit,
                target_kind=target_kind,
                target_id=target_id,
                category=category,
                severities=resolved_severities,
                statuses=resolved_statuses,
                tag=tag,
                author_actor_id=author_actor_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CautionListOutput(
            items=[
                CautionSummaryRow(
                    caution_id=item.caution_id,
                    target=_target_dto_from_row(item.target_kind, item.target_id),
                    category=CautionCategory(item.category),
                    severity=CautionSeverity(item.severity),
                    text=item.text,
                    workaround=item.workaround,
                    author_actor_id=item.author_actor_id,
                    tags=item.tags,
                    expires_at=item.expires_at,
                    propagate_to_children=item.propagate_to_children,
                    status=CautionStatus(item.status),
                    parent_id=item.parent_id,
                    superseded_by_caution_id=item.superseded_by_caution_id,
                    retired_reason=(
                        CautionRetireReason(item.retired_reason)
                        if item.retired_reason is not None
                        else None
                    ),
                    registered_at=item.registered_at,
                    last_status_changed_at=item.last_status_changed_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
