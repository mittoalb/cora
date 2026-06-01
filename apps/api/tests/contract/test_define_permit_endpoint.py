"""Contract tests for `POST /federation/permits` (define_permit endpoint).

201 happy path returns the generated permit_id; 422 covers pydantic-
layer rejections (missing body field, empty scope lists, invalid
discriminator, discriminator-mismatch flagged by FastAPI's Pydantic
discriminated-union); 400 covers decider-layer InvalidPermitScopeError;
422 also covers PermitScopeCollapseError (mapped to 422 by Federation
routes); 403 surfaces Authorize-port denial; 409 surfaces the
defensive PermitAlreadyExistsError genesis-collision guard.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.permit import PermitAlreadyExistsError
from cora.federation.errors import UnauthorizedError
from cora.federation.features.define_permit.route import (
    _get_handler as _get_define_permit_handler,  # pyright: ignore[reportPrivateUsage]
)

_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat()


def _body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "peer_facility_id": "aps-2bm",
        "direction": "Outbound",
        "allowed_credentials": [str(uuid4())],
        "allowed_payload_types": ["application/json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": _EXPIRES_AT,
        "terms": {
            "kind": "Outbound",
            "scopes": [{"kind": "dataset", "name": "public"}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_federation_permits_returns_201_with_permit_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/permits", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "permit_id" in body
    UUID(body["permit_id"])


@pytest.mark.contract
def test_post_federation_permits_accepts_inbound_terms() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/permits",
            json=_body(
                direction="Inbound",
                terms={
                    "kind": "Inbound",
                    "inbound_allowed_artifact_kinds": ["dataset"],
                },
            ),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_federation_permits_rejects_missing_required_body_field_with_422() -> None:
    """peer_facility_id missing -> Pydantic 422 before reaching the decider."""
    body = _body()
    del body["peer_facility_id"]
    with TestClient(create_app()) as client:
        response = client.post("/federation/permits", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_permits_rejects_empty_allowed_credentials_with_422() -> None:
    """min_length=1 on the request schema rejects empty lists at Pydantic."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/permits",
            json=_body(allowed_credentials=[]),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_permits_rejects_expires_at_in_past_with_400() -> None:
    """Decider-layer InvalidPermitScopeError bubbles as 400."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/permits",
            json=_body(expires_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat()),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_federation_permits_rejects_whitespace_only_peer_facility_id_with_400() -> None:
    """Pydantic min_length=1 doesn't trim, so '   ' reaches the decider
    and surfaces as InvalidPermitScopeError -> 400."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/permits",
            json=_body(peer_facility_id="   "),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_federation_permits_rejects_outbound_terms_collapse_with_422() -> None:
    """PermitScopeCollapseError is routed to 422 by federation routes."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/permits",
            json=_body(
                terms={
                    "kind": "Outbound",
                    "scopes": [{"kind": "dataset", "name": "public"}],
                    "read_scope": "ListMetadataOnly",
                    "onward_action_scope": "MayExportOffPlatform",
                },
            ),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_permits_returns_409_on_already_exists() -> None:
    """Defensive guard: a PermitAlreadyExistsError bubbles as 409 conflict."""
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise PermitAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_define_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/permits", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_federation_permits_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_define_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/permits", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
