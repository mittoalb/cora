"""Contract tests for `POST /federation/credentials/{credential_id}/rotation/complete`.

The happy-path Rotating -> Active transition cannot be exercised end-
to-end through the REST API in this slice because the upstream
`register_credential` + `start_credential_rotation` slice routes are
landed in sibling subtasks of Stage 2c-credential. These tests pin
the status-code mappings via dependency overrides; the handler-level
happy path is exercised by `test_complete_credential_rotation_handler`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import (
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialStatus,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.complete_credential_rotation.route import (
    _get_handler as _get_complete_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_complete_credential_rotation_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/complete",
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_complete_credential_rotation_returns_204_with_empty_body() -> None:
    """The slice takes no body fields; an explicit empty body is accepted."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/complete",
            json={},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_complete_credential_rotation_returns_404_on_unknown_credential() -> None:
    """A handler raising CredentialNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/complete",
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_complete_credential_rotation_returns_409_when_active() -> None:
    """A handler raising CredentialCannotRotateError surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=1),
            CredentialStatus.ACTIVE,
            "complete_rotation",
        )

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/complete",
        )
    assert response.status_code == 409
    assert "cannot complete_rotation" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_complete_credential_rotation_returns_409_when_revoked() -> None:
    """Revoked is terminal; complete surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=2),
            CredentialStatus.REVOKED,
            "complete_rotation",
        )

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/complete",
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_complete_credential_rotation_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/rotation/complete",
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_complete_credential_rotation_rejects_invalid_uuid_path_with_422() -> None:
    """A non-UUID path segment is rejected at the FastAPI Path layer."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/credentials/not-a-uuid/rotation/complete",
        )
    assert response.status_code == 422
