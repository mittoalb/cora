"""Contract tests for `POST /federation/credentials/{credential_id}/rotation/start`.

The happy-path Active -> Rotating transition is exercised end-to-end
in the handler tests; here we pin the status-code mappings via
dependency overrides plus Pydantic-layer rejection (missing
`new_secret_ref`, whitespace-only `new_secret_ref`, invalid UUID
path, extra fields under `extra=forbid`). Stage 2c-credential
sibling slices ship in the same change, so the upstream genesis is
not chained here.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import (
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialStatus,
    InvalidCredentialSecretRefError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.start_credential_rotation.route import (
    _get_handler as _get_start_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_start_credential_rotation_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={
                "new_secret_ref": "vault://pending/v2",
                "new_public_material_ref": "vault://pending/pub/v2",
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_credential_rotation_returns_204_without_public_material_ref() -> None:
    """`new_public_material_ref` is optional; an absent value is accepted."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": "vault://pending/v2"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_credential_rotation_returns_404_on_unknown_credential() -> None:
    """A handler raising CredentialNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": "vault://pending/v2"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_start_credential_rotation_returns_409_when_rotating() -> None:
    """A handler raising CredentialCannotRotateError surfaces as 409 (Rotating)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=1),
            CredentialStatus.ROTATING,
            "start_rotation",
        )

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": "vault://pending/v3"},
        )
    assert response.status_code == 409
    assert "cannot start_rotation" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_start_credential_rotation_returns_409_when_revoked() -> None:
    """Revoked is terminal; start_rotation surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=2),
            CredentialStatus.REVOKED,
            "start_rotation",
        )

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": "vault://pending/v2"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_start_credential_rotation_returns_409_when_new_ref_equals_current() -> None:
    """`start_rotation_same_ref` attempted tag also surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=3),
            CredentialStatus.ACTIVE,
            "start_rotation_same_ref",
        )

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": "vault://current/v1"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_start_credential_rotation_returns_400_on_invalid_secret_ref() -> None:
    """A handler raising InvalidCredentialSecretRefError surfaces as 400."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise InvalidCredentialSecretRefError("new_secret_ref", "   ")

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        # Pydantic min_length=1 lets a single space through; the
        # handler-level whitespace-only check then trips at the decider.
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": " "},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_start_credential_rotation_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": "vault://pending/v2"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_start_credential_rotation_rejects_missing_new_secret_ref_with_422() -> None:
    """Pydantic enforces `new_secret_ref` presence before reaching the handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_start_credential_rotation_rejects_empty_new_secret_ref_with_422() -> None:
    """Pydantic min_length=1 enforces non-empty ref BEFORE reaching the decider."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={"new_secret_ref": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_start_credential_rotation_rejects_extra_field_with_422() -> None:
    """`extra=forbid` on the request body schema rejects unknown fields."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/start",
            json={
                "new_secret_ref": "vault://pending/v2",
                "unexpected_field": "boom",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_start_credential_rotation_rejects_invalid_uuid_path_with_422() -> None:
    """A non-UUID path segment is rejected at the FastAPI Path layer."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/credentials/not-a-uuid/rotation/start",
            json={"new_secret_ref": "vault://pending/v2"},
        )
    assert response.status_code == 422
