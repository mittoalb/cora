"""HTTP route for the `register_asset` slice.

Pydantic request/response schemas + APIRouter for `POST /assets`.
The slice's BC-level wiring (`cora.equipment.routes.register_equipment_routes`)
includes this router on the FastAPI app.

Pydantic enforces `level` is a valid `AssetLevel` value at the API
boundary (Pydantic→422 on unknown level strings); the decider
trusts its inputs and only enforces domain invariants (hierarchy
rule, name VO).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH, AssetLevel
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.handler import IdempotentHandler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class RegisterAssetRequest(BaseModel):
    """Body for `POST /assets`.

    `level` accepts the StrEnum's PascalCase string values
    ("Enterprise" / "Site" / "Area" / "Unit" / "Assembly" /
    "Device"); Pydantic rejects unknowns with 422.

    `parent_id` is required for non-Enterprise levels and must be
    null for Enterprise — that's a domain invariant enforced by
    the decider (raises InvalidAssetParentError → 400), not by
    Pydantic, since the rule is conditional on `level`.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=ASSET_NAME_MAX_LENGTH,
        description="Display name for the new asset.",
    )
    level: AssetLevel = Field(
        ...,
        description=(
            "Hierarchical level. One of: Enterprise (root, requires "
            "null parent_id), Site, Area, Unit, Assembly, Device."
        ),
    )
    parent_id: UUID | None = Field(
        ...,
        description=(
            "Immediate parent in the hierarchy tree. Must be null "
            "for Enterprise-level assets; required for all others. "
            "Eventual-consistency: parent's existence is NOT verified."
        ),
    )


class RegisterAssetResponse(BaseModel):
    """Response body for `POST /assets`."""

    asset_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.register_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterAssetResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name OR "
                "hierarchy rule (Enterprise must have null parent_id; "
                "other levels must have non-null parent_id)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (unknown level, "
                "missing fields, malformed UUID) OR Idempotency-Key was "
                "reused with a different request body."
            ),
        },
    },
    summary="Register a new physical equipment asset",
)
async def post_assets(
    body: RegisterAssetRequest,
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
                "response instead of re-creating the asset."
            ),
        ),
    ] = None,
) -> RegisterAssetResponse:
    asset_id = await handler(
        RegisterAsset(name=body.name, level=body.level, parent_id=body.parent_id),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return RegisterAssetResponse(asset_id=asset_id)
