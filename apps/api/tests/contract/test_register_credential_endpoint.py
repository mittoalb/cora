"""Contract tests for `POST /federation/credentials` (register_credential endpoint).

201 happy path returns the generated credential_id; 422 covers
Pydantic-layer rejections (missing body field, empty fields via
min_length=1, malformed purpose enum, malformed datetime) AND the
decider-layer CredentialExpiredError (mapped to 422 by federation
routes); 400 covers the decider-layer
InvalidCredentialSecretRefError for whitespace-only fields that
slip past Pydantic min_length; 403 surfaces Authorize-port denial;
409 surfaces the defensive CredentialAlreadyExistsError genesis-
collision guard.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import CredentialAlreadyExistsError
from cora.federation.errors import UnauthorizedError
from cora.federation.features.register_credential.route import (
    _get_handler as _get_register_credential_handler,  # pyright: ignore[reportPrivateUsage]
)

_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC).isoformat()


def _body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "facility_code": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": "Signing",
        "secret_ref": "vault://kv/cora/federation/aps-2bm/signing#v1",
        "public_material_ref": "vault://kv/cora/federation/aps-2bm/signing/pub#v1",
        "expires_at": _EXPIRES_AT,
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_federation_credentials_returns_201_with_credential_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "credential_id" in body
    UUID(body["credential_id"])


@pytest.mark.contract
def test_post_federation_credentials_accepts_no_optional_fields() -> None:
    """public_material_ref and expires_at are optional."""
    body = _body()
    del body["public_material_ref"]
    del body["expires_at"]
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=body)
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_federation_credentials_rejects_missing_required_body_field_with_422() -> None:
    """facility_code missing -> Pydantic 422 before reaching the decider."""
    body = _body()
    del body["facility_code"]
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_credentials_rejects_empty_secret_ref_with_422() -> None:
    """min_length=1 on secret_ref rejects empty strings at Pydantic."""
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=_body(secret_ref=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_credentials_rejects_malformed_purpose_enum_with_422() -> None:
    """Pydantic rejects a purpose value outside the closed StrEnum."""
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=_body(purpose="NotAPurpose"))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_credentials_rejects_whitespace_only_secret_ref_with_400() -> None:
    """Pydantic min_length=1 doesn't trim, so '   ' reaches the decider
    and surfaces as InvalidCredentialSecretRefError -> 400."""
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=_body(secret_ref="   "))
    assert response.status_code == 400


@pytest.mark.contract
def test_post_federation_credentials_rejects_whitespace_only_facility_code_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=_body(facility_code="   "))
    assert response.status_code == 400


@pytest.mark.contract
def test_post_federation_credentials_rejects_whitespace_only_audience_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/federation/credentials", json=_body(audience="   "))
    assert response.status_code == 400


@pytest.mark.contract
def test_post_federation_credentials_rejects_expires_at_in_past_with_422() -> None:
    """Decider-layer CredentialExpiredError is routed to 422 by federation routes."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/credentials",
            json=_body(expires_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat()),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_credentials_returns_409_on_already_exists() -> None:
    """Defensive guard: a CredentialAlreadyExistsError bubbles as 409 conflict."""
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise CredentialAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_register_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/credentials", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_federation_credentials_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_register_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/credentials", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
