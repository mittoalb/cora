"""HTTP route for the `register_edition` slice.

`POST /editions` returns 201 + RegisterEditionResponse on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.edition import (
    EDITION_AFFILIATION_MAX_LENGTH,
    EDITION_CREATORS_MAX,
    EDITION_CREATORS_MIN,
    EDITION_LICENSE_MAX_LENGTH,
    EDITION_TITLE_MAX_LENGTH,
    EditionKind,
)
from cora.data.features.register_edition.command import (
    CreatorEntry,
    RegisterEdition,
)
from cora.data.features.register_edition.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class CreatorRequest(BaseModel):
    """One credited creator on the Edition."""

    actor_id: UUID = Field(
        ...,
        description="Identifier of the credited Actor (internal-opaque).",
    )
    affiliation: str | None = Field(
        default=None,
        max_length=EDITION_AFFILIATION_MAX_LENGTH,
        description=("Free-text affiliation string (institution / lab name). Optional."),
    )


class RegisterEditionRequest(BaseModel):
    """Body for `POST /editions`."""

    kind: EditionKind = Field(
        ...,
        description=(
            "Serialization-target kind. Closed enum: ROCrate, DataCite, "
            "Croissant, OAIS_AIP, OAIS_DIP, NeXus."
        ),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=EDITION_TITLE_MAX_LENGTH,
        description="Display title for the Edition.",
    )
    dataset_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description=(
            "Initial member Dataset ids. Each must resolve to a "
            "non-Discarded Dataset. Order is irrelevant; the payload "
            "sorts on the wire."
        ),
    )
    creators: list[CreatorRequest] = Field(
        ...,
        min_length=EDITION_CREATORS_MIN,
        max_length=EDITION_CREATORS_MAX,
        description=(
            "Ordered list of credited creators. Order is publication-"
            "significant (first-author convention); NEVER sorted."
        ),
    )
    license: str | None = Field(
        default=None,
        max_length=EDITION_LICENSE_MAX_LENGTH,
        description=(
            "Optional SPDX identifier. Required at seal-time for kind in {DataCite, Croissant}."
        ),
    )
    publication_year: int | None = Field(
        default=None,
        description=(
            "Optional explicit publication year (1900..current_year+5). "
            "Auto-derived at seal-time if not supplied."
        ),
    )
    publisher_facility_code: str | None = Field(
        default=None,
        description=(
            "Optional publisher Facility code (cross-deployment slug). "
            "Required and FacilityLookup-validated at seal-time."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterEditionResponse(BaseModel):
    """Response body for `POST /editions`."""

    edition_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.register_edition
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/editions",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterEditionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: malformed title, kind, "
                "license, publication_year, withdrawal reason, or "
                "creators tuple."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "A member dataset_id does not resolve.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": ("Registration-time conflict: a member Dataset is Discarded."),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Register a new Edition",
)
async def post_editions(
    body: RegisterEditionRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=("Optional client-supplied unique key per logical request."),
        ),
    ] = None,
) -> RegisterEditionResponse:
    edition_id = await handler(
        RegisterEdition(
            kind=body.kind.value,
            title=body.title,
            dataset_ids=frozenset(body.dataset_ids),
            creators=tuple(
                CreatorEntry(actor_id=c.actor_id, affiliation=c.affiliation) for c in body.creators
            ),
            license=body.license,
            publication_year=body.publication_year,
            publisher_facility_code=body.publisher_facility_code,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterEditionResponse(edition_id=edition_id)
