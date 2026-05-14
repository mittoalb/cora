"""HTTP route for the `get_subject` query slice.

`GET /subjects/{subject_id}` returns 200 + SubjectResponse on hit,
404 on miss. The handler returns `Subject | None`; the route maps
None to 404 via HTTPException (idiomatic in routes; the BC's
exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH
from cora.subject.features.get_subject.handler import Handler
from cora.subject.features.get_subject.query import GetSubject


class SubjectResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently
    (for example, a SubjectName invariant change doesn't break older
    clients). `status` is the StrEnum's string value (Received /
    Mounted / Measured / Removed / Returned / Stored / Discarded).
    `mounted_on_asset_id` (4f) is the Equipment.Asset id the Subject
    is currently mounted on, or null when not mounted (Received,
    post-dismount, Removed, or any terminal state).
    """

    id: UUID
    name: str = Field(..., max_length=SUBJECT_NAME_MAX_LENGTH)
    status: str
    mounted_on_asset_id: UUID | None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.get_subject
    return handler


router = APIRouter(tags=["subject"])


@router.get(
    "/subjects/{subject_id}",
    status_code=status.HTTP_200_OK,
    response_model=SubjectResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No subject exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a subject by id",
)
async def get_subjects(
    subject_id: Annotated[UUID, Path(description="Target subject's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> SubjectResponse:
    subject = await handler(
        GetSubject(subject_id=subject_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found",
        )
    return SubjectResponse(
        id=subject.id,
        name=subject.name.value,
        status=subject.status.value,
        mounted_on_asset_id=subject.mounted_on_asset_id,
    )
