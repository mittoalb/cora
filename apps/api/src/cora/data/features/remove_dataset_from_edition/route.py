"""HTTP route for the `remove_dataset_from_edition` slice.

`DELETE /editions/{edition_id}/datasets/{dataset_id}` returns 204
on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from cora.data.features.remove_dataset_from_edition.command import (
    RemoveDatasetFromEdition,
)
from cora.data.features.remove_dataset_from_edition.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.remove_dataset_from_edition
    return handler


router = APIRouter(tags=["data"])


@router.delete(
    "/editions/{edition_id}/datasets/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": ("Edition not found OR Dataset is not a member of this Edition."),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Edition not in Registered state OR removing this "
                "Dataset would leave the Edition with zero members."
            ),
        },
    },
    summary="Remove a Dataset from a Registered Edition",
)
async def delete_edition_dataset(
    edition_id: UUID,
    dataset_id: UUID,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> Response:
    await handler(
        RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=dataset_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
