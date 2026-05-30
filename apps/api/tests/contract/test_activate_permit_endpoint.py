"""Contract tests for `POST /federation/permits/{permit_id}/activate`."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.permit import PermitNotFoundError
from cora.federation.errors import UnauthorizedError
from cora.federation.features.activate_permit.route import (
    _get_handler as _get_activate_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_body() -> dict[str, Any]:
    return {
        "peer_facility_id": "aps-2bm",
        "direction": "Outbound",
        "allowed_credentials": [str(uuid4())],
        "allowed_payload_types": ["application/vnd.cora.dataset+json"],
        "permitted_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2027-05-30T12:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scope_set": [{"kind": "dataset", "name": "alpha", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }


def _register_permit(client: TestClient) -> str:
    response = client.post("/federation/permits", json=_register_body())
    assert response.status_code == 201, response.text
    return response.json()["permit_id"]


@pytest.mark.contract
def test_post_activate_permit_returns_204_on_defined_permit() -> None:
    with TestClient(create_app()) as client:
        permit_id = _register_permit(client)
        response = client.post(f"/federation/permits/{permit_id}/activate")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_activate_permit_returns_409_on_already_active() -> None:
    """Strict-not-idempotent: re-activating an Active permit -> 409."""
    with TestClient(create_app()) as client:
        permit_id = _register_permit(client)
        first = client.post(f"/federation/permits/{permit_id}/activate")
        assert first.status_code == 204, first.text
        response = client.post(f"/federation/permits/{permit_id}/activate")
    assert response.status_code == 409


@pytest.mark.contract
def test_post_activate_permit_returns_404_on_unknown_permit() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/federation/permits/{uuid4()}/activate")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_activate_permit_returns_422_for_malformed_path_uuid() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/permits/not-a-uuid/activate")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_activate_permit_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_activate_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{uuid4()}/activate")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_activate_permit_returns_404_via_handler_override() -> None:
    """Defensive: explicit not-found mapping via the handler-override hook."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_activate_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{uuid4()}/activate")
    assert response.status_code == 404
