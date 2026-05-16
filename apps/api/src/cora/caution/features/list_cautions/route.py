"""HTTP route for the `list_cautions` query slice.

`GET /cautions` accepts these optional query params: `cursor`, `limit`,
`target_kind`, `target_id`, `category`, `severity`, `min_severity`,
`status`, `tag`, `author_actor_id`. Returns
`{"items": [...], "next_cursor": "..." | null}`.

**Default behavior is `status=Active`.** Pass `status=all` to include
Superseded + Retired (per the design memo: Retired and Superseded
cautions never appear by default). Pass an exact status value to
narrow further.

**propagate_to_children is hint-only.** The flag rides through each
row unchanged; the endpoint does NOT walk Asset.parent_id chains to
return cautions inherited from parent assets. Watch item #8 reserves
that for either a denorm projection or a query-time join when a
consumer asks.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
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
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _target_dto_from_row(target_kind: str, target_id: UUID) -> TargetDTO:
    """Reconstruct the discriminated TargetDTO from the projection row's columns."""
    if target_kind == "Asset":
        return TargetAssetDTO(kind="Asset", id=target_id)
    return TargetProcedureDTO(kind="Procedure", id=target_id)


class CautionSummaryDTO(BaseModel):
    """One caution in a paginated list."""

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


class CautionListPageResponse(BaseModel):
    """Page of cautions plus opaque next-page cursor."""

    items: list[CautionSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.caution.list_cautions
    return handler


router = APIRouter(tags=["caution"])


@router.get(
    "/cautions",
    status_code=status.HTTP_200_OK,
    response_model=CautionListPageResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary=(
        "List cautions with cursor pagination + target / category / severity / "
        "min_severity / status / tag / author filters. Defaults to status=Active; "
        "pass status=all for the full set. propagate_to_children is hint-only "
        "(no Asset hierarchy walk)."
    ),
)
async def list_cautions(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    target_kind: Annotated[
        CautionTargetKindFilter | None,
        Query(description="Optional target-kind filter (Asset / Procedure)."),
    ] = None,
    target_id: Annotated[
        UUID | None,
        Query(description="Optional target-id filter; typically combined with target_kind."),
    ] = None,
    category: Annotated[
        CautionCategoryFilter | None,
        Query(description="Optional category filter (one of the 6 CautionCategory values)."),
    ] = None,
    severity: Annotated[
        CautionSeverityFilter | None,
        Query(description="Optional exact severity filter (Notice / Caution / Warning)."),
    ] = None,
    min_severity: Annotated[
        CautionSeverityFilter | None,
        Query(
            description=(
                "Optional severity-threshold filter; returns cautions with "
                "severity >= the threshold (Notice<Caution<Warning)."
            ),
        ),
    ] = None,
    status_filter: Annotated[
        CautionStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter; omit to default to 'Active' (hides "
                "Superseded + Retired). Pass 'all' to include every status, or "
                "an exact value (Active / Superseded / Retired) to narrow."
            ),
        ),
    ] = None,
    tag: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=CAUTION_TAG_MAX_LENGTH,
            description=(
                "Optional tag filter; matches any caution whose tags array contains this value."
            ),
        ),
    ] = None,
    author_actor_id: Annotated[
        UUID | None,
        Query(description="Optional author filter ('cautions I authored')."),
    ] = None,
) -> CautionListPageResponse:
    page = await handler(
        ListCautions(
            cursor=cursor,
            limit=limit,
            target_kind=target_kind,
            target_id=target_id,
            category=category,
            severity=severity,
            min_severity=min_severity,
            status=status_filter,
            tag=tag,
            author_actor_id=author_actor_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return CautionListPageResponse(
        items=[
            CautionSummaryDTO(
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


__all__ = ["CautionListPageResponse", "CautionSummaryDTO", "router"]
