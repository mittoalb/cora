"""HTTP route for the `register_subject` slice.

Pydantic request/response schemas + APIRouter for `POST /subjects`.
The slice's BC-level wiring (`cora.subject.routes.register_subject_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH
from cora.subject.features.register_subject.command import RegisterSubject
from cora.subject.features.register_subject.handler import IdempotentHandler


class RegisterSubjectRequest(BaseModel):
    """Body for `POST /subjects`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=SUBJECT_NAME_MAX_LENGTH,
        description="Display name for the new subject.",
    )


class RegisterSubjectResponse(BaseModel):
    """Response body for `POST /subjects`."""

    subject_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.subject.register_subject
    return handler


router = APIRouter(tags=["subject"])


@router.post(
    "/subjects",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterSubjectResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g. whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new subject",
)
async def post_subjects(
    body: RegisterSubjectRequest,
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
                "response instead of re-creating the subject."
            ),
        ),
    ] = None,
) -> RegisterSubjectResponse:
    subject_id = await handler(
        RegisterSubject(name=body.name),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterSubjectResponse(subject_id=subject_id)
