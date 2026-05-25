"""HTTP route for the `append_revision` slice.

Action endpoint at `POST /calibrations/{calibration_id}/revisions`.
201 + body `{revision_id}` on success. Idempotency-Key wrapped per
the design memo (agent-subscriber caller pattern needs exactly-once-
effective).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel, Field

from cora.calibration._calibration_dtos import SourceDTO, source_from_dto
from cora.calibration.aggregates.calibration import CalibrationStatus
from cora.calibration.features.append_revision.command import AppendRevision
from cora.calibration.features.append_revision.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AppendRevisionRequest(BaseModel):
    """Body for `POST /calibrations/{calibration_id}/revisions`."""

    value: dict[str, Any] = Field(
        ...,
        description=(
            "JSON-shaped revision value (for example, `{center: 1024.5}`). "
            "Validated STRICT against the calibration's quantity-specific "
            "VALUE_SCHEMA at the decider; missing required fields or "
            "additional properties raise 400."
        ),
    )
    status: CalibrationStatus = Field(
        ...,
        description=(
            "Per-revision posture: `Provisional` (initial estimate or "
            "early-data-derived) or `Verified` (blessed for production "
            "reconstructions). 2-tier; the 3-tier `Refined` middle is "
            "deferred to phase 12f."
        ),
    )
    source: SourceDTO = Field(
        ...,
        description=(
            "Tagged source provenance: `{kind: 'Measured', procedure_id}` "
            "/ `{kind: 'Computed', dataset_id}` / `{kind: 'Asserted', "
            "actor_id}`. The kind discriminator is required. Source FK "
            "targets are NOT cross-BC validated at the write path "
            "(eventual-consistency stance)."
        ),
    )
    decided_by_decision_id: UUID | None = Field(
        default=None,
        description=(
            "Optional Decision id that justified appending this revision "
            "(operator pivot, agent advisory). Maps to "
            "`prov:wasInformedBy` at the future PROV-O export adapter. "
            "Mirrors AdjustRun / StartRun / AbortRun pattern. NOT "
            "verified at the write path."
        ),
    )
    supersedes_revision_id: UUID | None = Field(
        default=None,
        description=(
            "Optional prior revision id (on the SAME aggregate) that this "
            "revision supersedes. Direct derivation edge per Q3 lock; "
            "saves consumers a graph walk vs traversal-only. Cross-"
            "aggregate supersession is forbidden: the supersedes target "
            "must exist on this calibration."
        ),
    )


class AppendRevisionResponse(BaseModel):
    """Response body for `POST /calibrations/{calibration_id}/revisions`."""

    revision_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.calibration.append_revision
    return handler


router = APIRouter(tags=["calibration"])


@router.post(
    "/calibrations/{calibration_id}/revisions",
    status_code=status.HTTP_201_CREATED,
    response_model=AppendRevisionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: value fails the quantity's "
                "value_schema, OR supersedes_revision_id does not match "
                "any revision on this aggregate."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No calibration exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Concurrent write to the same calibration stream "
                "conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema validation "
                "(for example unknown source `kind` discriminator) OR "
                "Idempotency-Key was reused with a different body."
            ),
        },
    },
    summary="Append a new revision to an existing Calibration",
)
async def post_calibration_revisions(
    calibration_id: Annotated[UUID, Path(description="Target calibration's id.")],
    body: AppendRevisionRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of appending a duplicate revision. "
                "REQUIRED in spirit for agent-subscriber callers."
            ),
        ),
    ] = None,
) -> AppendRevisionResponse:
    revision_id = await handler(
        AppendRevision(
            calibration_id=calibration_id,
            value=body.value,
            status=body.status,
            source=source_from_dto(body.source),
            decided_by_decision_id=body.decided_by_decision_id,
            supersedes_revision_id=body.supersedes_revision_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return AppendRevisionResponse(revision_id=revision_id)
