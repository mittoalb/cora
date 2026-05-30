"""Contract tests for `POST /federation/permits/{permit_id}/resume`.

Single-source reversible transition: `Suspended -> Active`. Strict-
not-idempotent: resuming an already-Active (or Defined / Revoked)
permit returns 409. No request body; principal identifies the actor.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.permit import (
    PermitCannotResumeError,
    PermitNotFoundError,
    PermitStatus,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.resume_permit.route import (
    _get_handler as _get_resume_permit_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_body() -> dict[str, Any]:
    return {
        "peer_facility_id": "aps-2bm",
        "direction": "Outbound",
        "allowed_credentials": [str(uuid4())],
        "allowed_payload_types": ["application/json"],
        "permitted_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scope_set": [{"kind": "dataset", "name": "public", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }


def _register_permit(client: TestClient) -> UUID:
    response = client.post("/federation/permits", json=_register_body())
    assert response.status_code == 201, response.text
    return UUID(response.json()["permit_id"])


def _drive_to_suspended(client: TestClient) -> UUID:
    permit_id = _register_permit(client)
    assert client.post(f"/federation/permits/{permit_id}/activate").status_code == 204
    assert client.post(f"/federation/permits/{permit_id}/suspend", json={}).status_code == 204
    return permit_id


@pytest.mark.contract
def test_post_resume_permit_returns_204_from_suspended() -> None:
    with TestClient(create_app()) as client:
        permit_id = _drive_to_suspended(client)
        response = client.post(f"/federation/permits/{permit_id}/resume")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_resume_permit_returns_409_when_status_is_defined() -> None:
    """`Defined` permits use `activate_permit`, not `resume_permit`."""
    with TestClient(create_app()) as client:
        permit_id = _register_permit(client)
        response = client.post(f"/federation/permits/{permit_id}/resume")
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_resume_permit_returns_409_when_already_active() -> None:
    """Strict-not-idempotent: resuming an already-Active permit returns 409."""
    with TestClient(create_app()) as client:
        permit_id = _register_permit(client)
        assert client.post(f"/federation/permits/{permit_id}/activate").status_code == 204
        response = client.post(f"/federation/permits/{permit_id}/resume")
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_resume_permit_returns_409_when_already_revoked() -> None:
    """`Revoked` is terminal: resume after revoke returns 409."""
    with TestClient(create_app()) as client:
        permit_id = _register_permit(client)
        assert client.post(f"/federation/permits/{permit_id}/revoke").status_code == 204
        response = client.post(f"/federation/permits/{permit_id}/resume")
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_resume_permit_supports_active_suspend_resume_cycle() -> None:
    """Active <-> Suspended is reversible; a second cycle still succeeds."""
    with TestClient(create_app()) as client:
        permit_id = _drive_to_suspended(client)
        first_resume = client.post(f"/federation/permits/{permit_id}/resume")
        assert first_resume.status_code == 204, first_resume.text
        assert client.post(f"/federation/permits/{permit_id}/suspend", json={}).status_code == 204
        second_resume = client.post(f"/federation/permits/{permit_id}/resume")
    assert second_resume.status_code == 204, second_resume.text


@pytest.mark.contract
def test_post_resume_permit_returns_404_for_unknown_id() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_resume_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{uuid4()}/resume")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_resume_permit_returns_409_on_cannot_resume_error() -> None:
    app = create_app()
    target_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitCannotResumeError(target_id, PermitStatus.ACTIVE)

    app.dependency_overrides[_get_resume_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{target_id}/resume")
    assert response.status_code == 409
    assert "resume" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_resume_permit_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_resume_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/permits/{uuid4()}/resume")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_resume_permit_rejects_malformed_permit_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/permits/not-a-uuid/resume")
    assert response.status_code == 422
