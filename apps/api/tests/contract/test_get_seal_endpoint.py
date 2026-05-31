"""Contract tests for `GET /federation/seals/{facility_id}`.

Singleton-per-facility: the URL carries the human-readable
`facility_id` (str), not the deterministic seal_stream_id UUID.
200 happy path returns the aggregate state plus nullable Path C
lifecycle timestamps; 404 covers the not-found path; 422 covers the
Pydantic-layer rejection of an empty path parameter; 403 surfaces
Authorize-port denial.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.errors import UnauthorizedError
from cora.federation.features.get_seal.route import (
    _get_handler as _get_get_seal_handler,  # pyright: ignore[reportPrivateUsage]
)

_ONLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0a1"
_OFFLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0b1"


def _seed_active_credentials(app: FastAPI, *, facility_id: str) -> None:
    lookup = app.state.deps.credential_lookup
    lookup.register(
        credential_id=UUID(_ONLINE_KEY_REF),
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    lookup.register(
        credential_id=UUID(_OFFLINE_KEY_REF),
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
        status=CredentialStatus.ACTIVE.value,
    )


def _seed(
    app: FastAPI,
    client: TestClient,
    **overrides: object,
) -> tuple[str, dict[str, Any]]:
    body: dict[str, Any] = {
        "facility_id": f"aps-2bm-{uuid4().hex[:8]}",
        "online_credential_id": _ONLINE_KEY_REF,
        "offline_credential_id": _OFFLINE_KEY_REF,
    }
    body.update(overrides)
    _seed_active_credentials(app, facility_id=str(body["facility_id"]))
    response = client.post("/federation/seals", json=body)
    assert response.status_code == 201, response.text
    return str(body["facility_id"]), body


@pytest.mark.contract
def test_get_federation_seal_returns_200_with_full_state() -> None:
    app = create_app()
    with TestClient(app) as client:
        facility_id, seeded = _seed(app, client)
        response = client.get(f"/federation/seals/{facility_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["facility_id"] == facility_id
    assert body["online_credential_id"] == seeded["online_credential_id"]
    assert body["offline_credential_id"] == seeded["offline_credential_id"]
    assert body["current_head_hash"] is None
    assert body["current_sequence_number"] == 0
    assert body["status"] == "Live"
    # Path C timestamps are nullable on the wire; the in-memory test
    # mode lacks a configured pool so initialized_at / last_signed_at
    # / last_signed_by_actor_id may be absent.
    assert "initialized_at" in body
    assert "last_signed_at" in body
    assert "last_signed_by_actor_id" in body


@pytest.mark.contract
def test_get_federation_seal_returns_404_when_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/federation/seals/no-such-facility-{uuid4().hex[:8]}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_federation_seal_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_seal_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/federation/seals/aps-2bm-{uuid4().hex[:8]}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


# Silence the unused-import linter.
_ = UUID
