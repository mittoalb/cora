"""HTTP route for the `get_dataset` query slice.

`GET /datasets/{dataset_id}` returns 200 + DatasetResponse on hit,
404 on miss.

The wire DTO mirrors the on-the-wire event payload shape (nested
`checksum` and `encoding` objects, sorted set fields) so client code
reading the registration response and the get response sees the
same structure.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.dataset import (
    DATASET_NAME_MAX_LENGTH,
)
from cora.data.features.get_dataset.handler import Handler
from cora.data.features.get_dataset.query import GetDataset
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class ChecksumResponse(BaseModel):
    """Bulk-content integrity hash on the response body."""

    algorithm: str
    value: str


class EncodingResponse(BaseModel):
    """Structured encoding descriptor on the response body."""

    media_type: str
    conforms_to: list[str]


class DatasetResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model. `conforms_to` and `derived_from` are
    sorted lists in the wire shape (matches the on-the-wire event
    payload sort).
    """

    id: UUID
    name: str = Field(..., max_length=DATASET_NAME_MAX_LENGTH)
    uri: str
    checksum: ChecksumResponse
    byte_size: int
    encoding: EncodingResponse
    producing_run_id: UUID | None
    subject_id: UUID | None
    derived_from: list[UUID]
    status: str


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.get_dataset
    return handler


router = APIRouter(tags=["data"])


@router.get(
    "/datasets/{dataset_id}",
    status_code=status.HTTP_200_OK,
    response_model=DatasetResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No dataset exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a dataset by id",
)
async def get_datasets(
    dataset_id: Annotated[UUID, Path(description="Target dataset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> DatasetResponse:
    dataset = await handler(
        GetDataset(dataset_id=dataset_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    return DatasetResponse(
        id=dataset.id,
        name=dataset.name.value,
        uri=dataset.uri.value,
        checksum=ChecksumResponse(
            algorithm=dataset.checksum.algorithm,
            value=dataset.checksum.value,
        ),
        byte_size=dataset.byte_size,
        encoding=EncodingResponse(
            media_type=dataset.encoding.media_type,
            conforms_to=sorted(dataset.encoding.conforms_to),
        ),
        producing_run_id=dataset.producing_run_id,
        subject_id=dataset.subject_id,
        derived_from=sorted(dataset.derived_from, key=str),
        status=dataset.status.value,
    )
