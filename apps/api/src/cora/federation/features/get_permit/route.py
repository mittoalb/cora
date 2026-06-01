"""HTTP route for the `get_permit` query slice.

`GET /federation/permits/{permit_id}` returns 200 + `PermitResponse`
on hit. Missing permits surface as 404 via the BC-level
`PermitNotFoundError` exception handler registered in
`federation.routes`.

The wire `terms` body is a discriminated Pydantic union
(`kind = "Outbound" | "Inbound"`) mirroring the `define_permit` /
projection split shape.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation._federation_dtos import FederationErrorDTO
from cora.federation.features.get_permit.handler import Handler, PermitView
from cora.federation.features.get_permit.query import GetPermit
from cora.infrastructure.routing import (
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class _ScopeRefResponse(BaseModel):
    """Wire shape for a `ScopeRef` in the outbound terms response."""

    kind: str
    name: str
    qualifier: str | None = None


class _OutboundTermsResponse(BaseModel):
    """Wire shape for outbound terms in the response."""

    kind: Literal["Outbound"]
    scopes: list[_ScopeRefResponse]
    read_scope: str
    onward_action_scope: str


class _InboundTermsResponse(BaseModel):
    """Wire shape for inbound terms in the response."""

    kind: Literal["Inbound"]
    inbound_allowed_artifact_kinds: list[str]
    accepted_canonicalization_versions: list[str]
    required_receipt_kinds: list[str]
    publisher_grant_correlation_handle: str | None = None


_TermsResponse = Annotated[
    _OutboundTermsResponse | _InboundTermsResponse,
    Field(discriminator="kind"),
]


class PermitResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Lifecycle timestamps are projection-sourced per Path C;
    `defined_at` is always present, transition timestamps stay `None`
    until their event fires.
    """

    id: UUID
    peer_facility_id: str
    direction: str
    allowed_credentials: list[UUID]
    allowed_payload_types: list[str]
    allowed_artifact_kinds: list[str]
    abi_tier_floor: str
    expires_at: datetime
    defined_by_actor_id: UUID
    status: str
    terms: _TermsResponse
    defined_at: datetime
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    resumed_at: datetime | None = None
    revoked_at: datetime | None = None


def _terms_from_view(view: PermitView) -> _TermsResponse:
    if view.terms_kind == "Outbound":
        scopes = view.scopes or []
        return _OutboundTermsResponse(
            kind="Outbound",
            scopes=[
                _ScopeRefResponse(
                    kind=s["kind"],
                    name=s["name"],
                    qualifier=s.get("qualifier"),
                )
                for s in scopes
            ],
            read_scope=view.read_scope or "",
            onward_action_scope=view.onward_action_scope or "",
        )
    return _InboundTermsResponse(
        kind="Inbound",
        inbound_allowed_artifact_kinds=view.inbound_allowed_artifact_kinds or [],
        accepted_canonicalization_versions=view.accepted_canonicalization_versions or [],
        required_receipt_kinds=view.required_receipt_kinds or [],
        publisher_grant_correlation_handle=view.publisher_grant_correlation_handle,
    )


def _response_from_view(view: PermitView) -> PermitResponse:
    return PermitResponse(
        id=view.permit_id,
        peer_facility_id=view.peer_facility_id,
        direction=view.direction,
        allowed_credentials=list(view.allowed_credentials),
        allowed_payload_types=list(view.allowed_payload_types),
        allowed_artifact_kinds=list(view.allowed_artifact_kinds),
        abi_tier_floor=view.abi_tier_floor,
        expires_at=view.expires_at,
        defined_by_actor_id=view.defined_by_actor_id,
        status=view.status,
        terms=_terms_from_view(view),
        defined_at=view.defined_at,
        activated_at=view.activated_at,
        suspended_at=view.suspended_at,
        resumed_at=view.resumed_at,
        revoked_at=view.revoked_at,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.get_permit
    return handler


router = APIRouter(tags=["federation"])


@router.get(
    "/federation/permits/{permit_id}",
    status_code=status.HTTP_200_OK,
    response_model=PermitResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": FederationErrorDTO,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": FederationErrorDTO,
            "description": "No Permit exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": FederationErrorDTO,
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a federation Permit by id",
)
async def get_federation_permit(
    permit_id: Annotated[UUID, Path(description="Target permit's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> PermitResponse:
    view = await handler(
        GetPermit(permit_id=permit_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return _response_from_view(view)
