"""HTTP route for the `add_asset_port` slice (Phase 5h).

Action endpoint at `POST /assets/{asset_id}/add_port`. Body
carries `port_name`, `direction` (Input/Output), `signal_type`.
204 No Content on success. Same action-endpoint pattern as
`add_asset_family`.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import (
    PORT_NAME_MAX_LENGTH,
    PORT_SIGNAL_TYPE_MAX_LENGTH,
    PortDirection,
)
from cora.equipment.features.add_asset_port.command import AddAssetPort
from cora.equipment.features.add_asset_port.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddAssetPortRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/add_port`.

    All three fields are required. Pydantic enforces non-empty
    name/signal_type at the boundary; the AssetPort VO then trims
    and re-validates length within the decider.
    """

    port_name: str = Field(
        ...,
        min_length=1,
        max_length=PORT_NAME_MAX_LENGTH,
        description=(
            "Port name within the Asset's scope (e.g., 'trigger_in', "
            "'encoder_a', 'sync_clock'). Must be unique among the "
            "Asset's existing ports."
        ),
    )
    direction: Literal["Input", "Output"] = Field(
        ...,
        description="Port direction: 'Input' or 'Output' (PortDirection enum value).",
    )
    signal_type: str = Field(
        ...,
        min_length=1,
        max_length=PORT_SIGNAL_TYPE_MAX_LENGTH,
        description=(
            "Operator-supplied signal type (free text 1-50 chars). "
            "Common values: 'TTL', 'LVDS', 'Encoder', 'Network', "
            "'Sync', 'Optical'."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_asset_port
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/add_port",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Port name or signal_type is empty / whitespace-only / "
                "exceeds the configured max length after trimming "
                "(InvalidAssetPortNameError or "
                "InvalidAssetPortSignalTypeError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset cannot accept the port under current conditions "
                "(asset is Decommissioned, OR a port with the same name "
                "already exists), OR a concurrent write to the same "
                "asset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, invalid direction enum, "
                "etc.)."
            ),
        },
    },
    summary="Add a typed port to an existing Asset's port set",
)
async def post_assets_add_port(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: AddAssetPortRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddAssetPort(
            asset_id=asset_id,
            port_name=body.port_name,
            direction=PortDirection(body.direction),
            signal_type=body.signal_type,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
