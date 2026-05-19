"""HTTP route for the `list_cautions` query slice.

`GET /cautions` accepts these optional query params: `cursor`,
`limit`, `target_kind`, `target_id`, `category`, `severity` (one
or more; multi-value), `min_severity` (Notice<Caution<Warning
ladder convenience), `status` (one or more; multi-value; plus the
`all` sentinel that disables the filter), `tag`, `author_actor_id`.

## Status default + 'all' sentinel

Omitted `status` defaults to `[Active]` so operators don't see
retired or superseded cautions cluttering the list. Pass
`?status=all` to opt into the full set (Active + Superseded +
Retired). Pass one or more explicit values (`?status=Active&status=Superseded`)
to narrow.

`all` and explicit status values cannot be combined in the same
request; doing so returns 422.

## Severity translation

The route accepts two ways to filter on severity:

  - `?severity=Caution&severity=Warning` — multi-value, exact match
    against the candidate set.
  - `?min_severity=Caution` — ladder convenience that expands to
    `[Caution, Warning]` server-side per the Notice<Caution<Warning
    ordering.

These two cannot be combined; doing so returns 422 (the old
single-string SQL silently returned the intersection, which was
always empty for conflicting inputs).

The application handler sees only the canonical `severities`
list; both UX shapes converge to the same internal contract per
the `cora.infrastructure.list_query` growth-rule discipline.

## propagate_to_children is hint-only

The flag rides through each row unchanged; the endpoint does NOT
walk Asset.parent_id chains to return cautions inherited from
parent assets. Watch item #8 reserves that for either a denorm
projection or a query-time join when a consumer asks.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)

# Route-surface type: real status values plus the 'all' sentinel that
# translates to "no filter" at this layer. The query dataclass +
# application handler never see 'all' (per the growth-rule discipline
# documented on `cora.infrastructure.list_query`).
_RouteStatusParam = Literal["Active", "Superseded", "Retired", "all"]

# Notice<Caution<Warning ladder. min_severity='Caution' expands to
# the suffix [Caution, Warning]; the canonical handler-facing
# `severities` list is the result.
_SEVERITY_LADDER: dict[CautionSeverityFilter, list[CautionSeverityFilter]] = {
    "Notice": ["Notice", "Caution", "Warning"],
    "Caution": ["Caution", "Warning"],
    "Warning": ["Warning"],
}


def _resolve_severities(
    severity: list[CautionSeverityFilter] | None,
    min_severity: CautionSeverityFilter | None,
) -> list[CautionSeverityFilter] | None:
    """Translate user-facing severity inputs into the canonical list.

    Raises 422 when both `severity` (multi-value exact) and
    `min_severity` (ladder convenience) are passed: the old SQL
    silently returned the intersection (empty for conflicting
    inputs), which was a latent bug.
    """
    has_severity = severity is not None and len(severity) > 0
    has_min = min_severity is not None
    if has_severity and has_min:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Pass either `severity` (one or more exact values) or "
                "`min_severity` (Notice<Caution<Warning ladder), not both."
            ),
        )
    if has_severity:
        return severity
    if has_min:
        # mypy/pyright: min_severity is not None here.
        assert min_severity is not None
        return list(_SEVERITY_LADDER[min_severity])
    return None


def _resolve_statuses(
    status_params: list[_RouteStatusParam] | None,
) -> list[CautionStatusFilter] | None:
    """Translate user-facing status inputs into the canonical list.

    None (omitted) -> default ['Active'] (operator UX: hide retired
    + superseded).

    Exactly ['all'] -> None (disable the filter; show every status).
    'all' mixed with real values raises 422 (ambiguous).

    Otherwise -> the explicit list (after validating no 'all' sneaked
    in alongside real values).
    """
    if status_params is None or len(status_params) == 0:
        return ["Active"]
    has_all = "all" in status_params
    if has_all and len(status_params) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Pass either `status=all` (disable filter) or one or "
                "more explicit status values, not both."
            ),
        )
    if has_all:
        return None
    # All remaining entries are real CautionStatusFilter values.
    return [v for v in status_params if v != "all"]


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
                "malformed OR `severity` and `min_severity` were both "
                "passed OR `status=all` was mixed with explicit status values."
            ),
        },
    },
    summary=(
        "List cautions with cursor pagination + target / category / severity / "
        "min_severity / status / tag / author filters. Defaults to status=[Active]; "
        "pass status=all for the full set. propagate_to_children is hint-only "
        "(no Asset hierarchy walk)."
    ),
)
async def list_cautions(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
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
        list[CautionSeverityFilter] | None,
        Query(
            description=(
                "Optional exact severity filter; multi-value. "
                "Pass once for a single value, repeat for any-of "
                "(`?severity=Caution&severity=Warning`). Cannot be "
                "combined with `min_severity`."
            ),
        ),
    ] = None,
    min_severity: Annotated[
        CautionSeverityFilter | None,
        Query(
            description=(
                "Optional severity-threshold filter; expands to the "
                "matching suffix of the Notice<Caution<Warning ladder. "
                "Cannot be combined with `severity`."
            ),
        ),
    ] = None,
    status_params: Annotated[
        list[_RouteStatusParam] | None,
        Query(
            alias="status",
            description=(
                "Optional status filter; multi-value. Omit to default "
                "to `[Active]` (hides Superseded + Retired). Pass "
                "`all` alone to include every status, or one or more "
                "explicit values to narrow. `all` cannot be mixed with "
                "explicit values."
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
    severities = _resolve_severities(severity, min_severity)
    statuses = _resolve_statuses(status_params)
    page = await handler(
        ListCautions(
            cursor=cursor,
            limit=limit,
            target_kind=target_kind,
            target_id=target_id,
            category=category,
            severities=severities,
            statuses=statuses,
            tag=tag,
            author_actor_id=author_actor_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
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
