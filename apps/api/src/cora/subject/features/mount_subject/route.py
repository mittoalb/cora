"""HTTP route for the `mount_subject` slice.

Action endpoint at `POST /subjects/{subject_id}/mount`. Same
action-endpoint pattern as `deactivate_actor`: the verb in the URL
matches the command name; future transition slices (measure, remove,
return/store/discard) get parallel `/subjects/{id}/<verb>` URLs.

204 No Content on success (action verb, no body to return).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.mount_subject
    return handler


router = APIRouter(tags=["subject"])


@router.post(
    "/subjects/{subject_id}/mount",
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
                "Subject is not in `Received` state (mount requires Received), "
                "OR a concurrent write to the same subject stream conflicted "
                "(optimistic concurrency)."
            ),
        },
    },
    summary="Mount an existing subject on the apparatus",
)
async def post_subjects_mount(
    subject_id: Annotated[UUID, Path(description="Target subject's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        MountSubject(subject_id=subject_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
