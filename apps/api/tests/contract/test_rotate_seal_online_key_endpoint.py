"""Contract tests for `POST /federation/seals/{facility_id}/online-key/rotate`.

Live -> Live mid-lifecycle transition that swaps the online (warm) key.
Strict-not-idempotent: re-rotating to the same ref raises 409; rotating
against a Republishing Seal raises 409; rotating to a ref equal to
`offline_credential_id` raises 422 (key-separation invariant).

The cross-BC happy-path (SealOnlineKeyRotated + DecisionRegistered
atomic write) is exercised by the handler tests and the integration
test against real Postgres. These tests pin the status-code mappings
via dependency overrides; the route-layer happy path returns 204 on
the handler's None return.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotRotateError,
    SealCredentialNotTrustAnchorError,
    SealKeyCollisionError,
    SealNotFoundError,
    SealStatus,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.rotate_seal_online_key.route import (
    _get_handler as _get_rotate_seal_online_key_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": str(uuid4()), "signed_by_offline_root": True},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_404_when_seal_not_found() -> None:
    """A handler raising SealNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealNotFoundError("aps-2bm")

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": str(uuid4()), "signed_by_offline_root": True},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_409_when_republishing() -> None:
    """Strict-not-idempotent: rotating against a Republishing Seal raises
    SealCannotRotateError which surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotRotateError("aps-2bm", SealStatus.REPUBLISHING)

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": str(uuid4()), "signed_by_offline_root": True},
        )
    assert response.status_code == 409
    assert "rotate" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_409_on_noop_rotation() -> None:
    """No-op rotation (new ref equals current online ref) raises
    SealCannotRotateError which surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotRotateError("aps-2bm", SealStatus.LIVE)

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": str(uuid4()), "signed_by_offline_root": True},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_422_on_key_collision() -> None:
    """Key-separation invariant violation surfaces as 422."""
    app = create_app()
    shared_ref = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealKeyCollisionError(facility_id="aps-2bm", shared_credential_id=shared_ref)

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={
                "new_online_credential_id": str(shared_ref),
                "signed_by_offline_root": True,
            },
        )
    assert response.status_code == 422
    assert "differ" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_409_on_credential_not_trust_anchor() -> None:
    """SealCredentialNotTrustAnchorError (structural cross-tenant defense
    via set-membership against Facility.trust_anchor_credential_ids)
    surfaces as 409 conflict per the federation routes mapping."""
    app = create_app()
    candidate_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCredentialNotTrustAnchorError(
            facility_id="aps-2bm",
            credential_id=candidate_id,
            key_ref_role="online",
        )

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={
                "new_online_credential_id": str(candidate_id),
                "signed_by_offline_root": True,
            },
        )
    assert response.status_code == 409
    assert "trust anchor" in response.json()["detail"]


@pytest.mark.contract
def test_post_rotate_seal_online_key_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": str(uuid4()), "signed_by_offline_root": True},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_rotate_seal_online_key_rejects_missing_body_with_422() -> None:
    """`new_online_credential_id` is required; an empty body is rejected at the
    Pydantic layer with 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_rotate_seal_online_key_rejects_malformed_uuid_with_422() -> None:
    """A non-UUID `new_online_credential_id` is rejected at the Pydantic layer."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": "not-a-uuid", "signed_by_offline_root": True},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_rotate_seal_online_key_rejects_missing_signed_by_offline_root_with_422() -> None:
    """`signed_by_offline_root` is required (no default); a body without it is
    rejected at the Pydantic layer with 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={"new_online_credential_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_rotate_seal_online_key_rejects_extra_body_field_with_422() -> None:
    """Body model is strict (model_config={'extra': 'forbid'}): unknown fields
    are rejected at the Pydantic layer."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={
                "new_online_credential_id": str(uuid4()),
                "signed_by_offline_root": True,
                "unknown_field": "y",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_rotate_seal_online_key_accepts_uuid_v4_ref() -> None:
    """A standard UUID4 is accepted by the route body model."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_rotate_seal_online_key_handler] = lambda: fake_handler
    valid_ref = uuid4()
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/online-key/rotate",
            json={
                "new_online_credential_id": str(valid_ref),
                "signed_by_offline_root": True,
            },
        )
    assert response.status_code == 204, response.text
    # UUID round-trip to confirm the value parses
    UUID(str(valid_ref))
