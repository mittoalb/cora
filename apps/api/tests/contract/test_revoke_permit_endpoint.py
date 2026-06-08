"""Contract tests for `POST /federation/permits/{permit_id}/revoke`.

Widest-source terminal transition: any non-Revoked status (Defined,
Active, Suspended) -> Revoked. Strict-not-idempotent (re-revoke
returns 409). No request body; principal identifies the actor.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.permit import (
    PermitCannotRevokeError,
    PermitNotFoundError,
    PermitStatus,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.revoke_permit.route import (
    _get_handler as _get_revoke_permit_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_body() -> dict[str, Any]:
    return {
        "peer_facility_code": "aps-2bm",
        "direction": "Outbound",
        "allowed_credential_ids": [str(uuid4())],
        "allowed_payload_types": ["application/json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scopes": [{"kind": "dataset", "name": "public", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }


def _define_permit(client: TestClient) -> UUID:
    response = client.post("/federation/permits", json=_register_body())
    assert response.status_code == 201, response.text
    return UUID(response.json()["permit_id"])


@pytest.mark.contract
def test_post_revoke_permit_returns_204_from_defined() -> None:
    with TestClient(create_app()) as client:
        permit_id = _define_permit(client)
        response = client.post(f"/federation/permits/{permit_id}/revoke")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_permit_returns_204_from_active() -> None:
    with TestClient(create_app()) as client:
        permit_id = _define_permit(client)
        activate = client.post(f"/federation/permits/{permit_id}/activate")
        assert activate.status_code == 204, activate.text
        response = client.post(f"/federation/permits/{permit_id}/revoke")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_permit_returns_204_from_suspended() -> None:
    with TestClient(create_app()) as client:
        permit_id = _define_permit(client)
        assert client.post(f"/federation/permits/{permit_id}/activate").status_code == 204
        suspend = client.post(f"/federation/permits/{permit_id}/suspend", json={})
        assert suspend.status_code == 204, suspend.text
        response = client.post(f"/federation/permits/{permit_id}/revoke")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_permit_returns_409_when_already_revoked() -> None:
    """Strict-not-idempotent: re-revoke returns 409."""
    with TestClient(create_app()) as client:
        permit_id = _define_permit(client)
        first = client.post(f"/federation/permits/{permit_id}/revoke")
        assert first.status_code == 204, first.text
        second = client.post(f"/federation/permits/{permit_id}/revoke")
    assert second.status_code == 409, second.text


@pytest.mark.contract
def test_post_revoke_permit_returns_404_for_unknown_id() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_revoke_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{uuid4()}/revoke")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revoke_permit_returns_409_on_cannot_revoke_error() -> None:
    app = create_app()
    target_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitCannotRevokeError(target_id, PermitStatus.REVOKED)

    app.dependency_overrides[_get_revoke_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{target_id}/revoke")
    assert response.status_code == 409
    assert "revoke" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_revoke_permit_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_revoke_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{uuid4()}/revoke")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_revoke_permit_rejects_malformed_permit_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/permits/not-a-uuid/revoke")
    assert response.status_code == 422
