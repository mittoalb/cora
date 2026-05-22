"""HTTP route for the `get_plan` query slice.

`GET /plans/{plan_id}` returns 200 + PlanResponse on hit, 404 on
miss. The handler returns `PlanView | None`; the route maps None to
404 via HTTPException.

Per gate-review Q4: response shape is CURRENT state only
`{id, name, practice_id, asset_ids, status, version, lifecycle
timestamps}`. Bind-time audit snapshots (method_id, snapshots) are
not exposed here; if pilot needs them, they ship as a separate audit
query (deferred 6e-3+).

`asset_ids` serializes as a sorted list of UUIDs (deterministic
ordering for client diffs / cache validation).

`created_at` / `versioned_at` / `deprecated_at` are sourced from the
`proj_recipe_plan_summary` projection, not from aggregate state
(Path C). Null semantics under eventual
consistency: read together with `status`. A 200 with a populated
`status` but null timestamp means projection lag, never a missing
transition. A 404 means the Plan aggregate itself does not exist.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.plan import PLAN_NAME_MAX_LENGTH
from cora.recipe.features.get_plan.handler import Handler
from cora.recipe.features.get_plan.query import GetPlan


class PlanResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value (Defined / Versioned / Deprecated). `asset_ids`
    is sorted by UUID string form (deterministic). `version` is the
    operator-supplied label of the most recent version_plan call
    (null until first version). `created_at` / `versioned_at` /
    `deprecated_at` are projection-sourced lifecycle timestamps
    (Path C); see module docstring for
    null-semantics.
    """

    id: UUID
    name: str = Field(..., max_length=PLAN_NAME_MAX_LENGTH)
    practice_id: UUID
    asset_ids: list[UUID]
    status: str
    version: str | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.get_plan
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/plans/{plan_id}",
    status_code=status.HTTP_200_OK,
    response_model=PlanResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No plan exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a plan by id",
)
async def get_plans(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> PlanResponse:
    view = await handler(
        GetPlan(plan_id=plan_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )
    plan = view.plan
    timestamps = view.timestamps
    return PlanResponse(
        id=plan.id,
        name=plan.name.value,
        practice_id=plan.practice_id,
        asset_ids=sorted(plan.asset_ids, key=str),
        status=plan.status.value,
        version=plan.version,
        created_at=timestamps.created_at if timestamps is not None else None,
        versioned_at=timestamps.versioned_at if timestamps is not None else None,
        deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
    )
