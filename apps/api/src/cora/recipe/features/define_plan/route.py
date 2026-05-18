"""HTTP route for the `define_plan` slice.

Pydantic request/response schemas + APIRouter for `POST /plans`.
The slice's BC-level wiring (`cora.recipe.routes.register_recipe_routes`)
includes this router on the FastAPI app.

`practice_id` and entries in `asset_ids` are required UUIDs.
Existence is verified at handler-load time (Practice / Method via
Practice / each Asset). Misses surface as HTTP 404 via the
respective aggregates' NotFoundError → exception handler. State-of-
existing-thing checks (Deprecated upstream, Decommissioned Asset,
family superset) happen in the decider and surface as 409.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.plan import PLAN_NAME_MAX_LENGTH
from cora.recipe.features.define_plan.command import DefinePlan
from cora.recipe.features.define_plan.handler import IdempotentHandler


class DefinePlanRequest(BaseModel):
    """Body for `POST /plans`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=PLAN_NAME_MAX_LENGTH,
        description="Display name for the new plan.",
    )
    practice_id: UUID = Field(
        ...,
        description=(
            "Practice id this Plan binds. Existence verified at handler-"
            "load time; missing → 404. Practice's status verified by "
            "decider (Deprecated → 409)."
        ),
    )
    asset_ids: set[UUID] = Field(
        ...,
        min_length=1,
        description=(
            "Set of Asset ids this Plan binds. Multi-asset binding; at "
            "least one required. Each Asset's existence verified at "
            "handler-load time (missing → 404); decider checks no Asset "
            "is Decommissioned (→ 409) and that the union of bound "
            "Assets' families covers the Method's needed_families."
        ),
    )


class DefinePlanResponse(BaseModel):
    """Response body for `POST /plans`."""

    plan_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.recipe.define_plan
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans",
    status_code=status.HTTP_201_CREATED,
    response_model=DefinePlanResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": ("Referenced Practice, Method (via Practice), or Asset does not exist."),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Binding rejected: upstream Practice or Method is "
                "Deprecated, a bound Asset is Decommissioned, or the "
                "bound Assets' families don't cover the Method's "
                "needed_families."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-"
                "Key was reused with a different request body."
            ),
        },
    },
    summary="Define a new Plan: bind a Practice to Asset instances",
)
async def post_plans(
    body: DefinePlanRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the plan."
            ),
        ),
    ] = None,
) -> DefinePlanResponse:
    plan_id = await handler(
        DefinePlan(
            name=body.name,
            practice_id=body.practice_id,
            asset_ids=frozenset(body.asset_ids),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return DefinePlanResponse(plan_id=plan_id)
