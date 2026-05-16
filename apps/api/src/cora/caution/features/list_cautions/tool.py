"""MCP tool for the `list_cautions` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.caution._bootstrap import SYSTEM_PRINCIPAL_ID
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
from cora.infrastructure.observability import current_correlation_id


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
    parent_caution_id: UUID | None = None
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
            "(one of the 6 CautionCategory values), `severity` (Notice / "
            "Caution / Warning), `min_severity` (threshold; >= "
            "Notice<Caution<Warning), `status` (defaults to 'Active'; "
            "pass 'all' to include Superseded + Retired), `tag` (exact "
            "match in the tags array), `author_actor_id`. Pass `cursor` "
            "from a previous page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_cautions_tool(  # pyright: ignore[reportUnusedFunction]
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
        severity: Annotated[
            CautionSeverityFilter | None,
            Field(description="Optional exact severity filter."),
        ] = None,
        min_severity: Annotated[
            CautionSeverityFilter | None,
            Field(
                description=(
                    "Optional severity-threshold filter; returns cautions with "
                    "severity >= the threshold."
                ),
            ),
        ] = None,
        status: Annotated[
            CautionStatusFilter | None,
            Field(
                description=(
                    "Optional status filter; defaults to 'Active'. Pass 'all' "
                    "to include every status."
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
        handler = get_handler()
        page = await handler(
            ListCautions(
                cursor=cursor,
                limit=limit,
                target_kind=target_kind,
                target_id=target_id,
                category=category,
                severity=severity,
                min_severity=min_severity,
                status=status,
                tag=tag,
                author_actor_id=author_actor_id,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
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
                    parent_caution_id=item.parent_caution_id,
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
