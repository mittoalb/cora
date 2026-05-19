"""HTTP route for the `measure_subject` slice.

Action endpoint at `POST /subjects/{subject_id}/measure`. Same
action-endpoint pattern as `mount_subject`: the verb in the URL
matches the command name. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.subject.features.measure_subject.command import MeasureSubject
from cora.subject.features.measure_subject.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.measure_subject
    return handler


router = APIRouter(tags=["subject"])


@router.post(
    "/subjects/{subject_id}/measure",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No subject exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Subject is not in `Mounted` state (measure requires Mounted), "
                "OR a concurrent write to the same subject stream conflicted "
                "(optimistic concurrency)."
            ),
        },
    },
    summary="Record a measurement on an existing subject",
)
async def post_subjects_measure(
    subject_id: Annotated[UUID, Path(description="Target subject's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        MeasureSubject(subject_id=subject_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
