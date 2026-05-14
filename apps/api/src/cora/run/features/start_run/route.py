"""HTTP route for the `start_run` slice.

Pydantic request/response schemas + APIRouter for `POST /runs`.
The slice's BC-level wiring (`cora.run.routes.register_run_routes`)
includes this router on the FastAPI app.

`plan_id` is required UUID. `subject_id` is optional UUID (null /
omitted for dark-field / flat-field calibration runs per beamline-
domain convention). Existence verified at handler-load time (Plan
+ Practice via Plan + Method via Practice + each bound Asset +
Subject if given). Misses surface as HTTP 404 via the respective
aggregates' NotFoundError → exception handler. State-of-existing-
thing checks (Plan Deprecated, Subject not mountable, Asset
Decommissioned, capabilities not satisfied at Run-start) surface
as 409.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.handler import IdempotentHandler


class StartRunRequest(BaseModel):
    """Body for `POST /runs`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=RUN_NAME_MAX_LENGTH,
        description="Display name for the new run.",
    )
    plan_id: UUID = Field(
        ...,
        description=(
            "Plan id this Run executes. Existence verified at handler-"
            "load time; missing → 404. Plan's status verified by decider "
            "(Deprecated → 409). Capability superset re-validated against "
            "current Asset state (drift since Plan-bind → 409)."
        ),
    )
    subject_id: UUID | None = Field(
        default=None,
        description=(
            "Subject being measured. Omit (or null) for dark-field / "
            "flat-field calibration runs. If given, Subject must be in "
            "Mounted or Measured state (else 409)."
        ),
    )
    raid: str | None = Field(
        default=None,
        max_length=2048,
        description=(
            "Research Activity Identifier (ISO 23527) for the project "
            "this Run belongs to. Optional opaque string carried verbatim. "
            "Used at PROV-O / DataCite export boundaries to link Datasets, "
            "Subjects, Instruments, and people for cross-facility provenance."
        ),
    )
    override_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Operator-supplied overrides on top of `Plan.default_parameters` "
            "(RFC 7396 merge semantics). The post-merge result is "
            "validated against the owning Method's `parameters_schema`; "
            "STRICT when the Method declares no schema (non-empty "
            "effective parameters rejected with 400; declare an empty "
            "`{}` schema for parameter-less Methods, or omit overrides "
            "and ensure Plan defaults are empty). Phase 6g-c."
        ),
    )
    triggered_by: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Free-form text capturing what initiated this Run "
            "(operator-manual, scheduler id, prior-run id, automation). "
            "Optional. Phase 6g-c."
        ),
    )


class StartRunResponse(BaseModel):
    """Response body for `POST /runs`."""

    run_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.run.start_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs",
    status_code=status.HTTP_201_CREATED,
    response_model=StartRunResponse,
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
            "description": (
                "Referenced Plan, Practice (via Plan), Method (via "
                "Practice), Asset (via Plan), or Subject does not exist."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Run-start rejected: Plan is Deprecated, Subject is not "
                "in Mounted or Measured, a bound Asset is Decommissioned, "
                "or the bound Assets' current capabilities don't cover "
                "the Method's needs_capabilities."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-"
                "Key was reused with a different request body."
            ),
        },
    },
    summary="Start a new Run: bind a Plan + (optional) Subject",
)
async def post_runs(
    body: StartRunRequest,
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
                "response instead of starting a duplicate run."
            ),
        ),
    ] = None,
) -> StartRunResponse:
    run_id = await handler(
        StartRun(
            name=body.name,
            plan_id=body.plan_id,
            subject_id=body.subject_id,
            raid=body.raid,
            override_parameters=body.override_parameters,
            triggered_by=body.triggered_by,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return StartRunResponse(run_id=run_id)
