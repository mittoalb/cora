"""Contract tests for `POST /federation/seals` (initialize_seal endpoint).

201 happy path returns the deterministic seal_stream_id + facility_id;
422 covers Pydantic-layer rejections (missing body field, malformed
UUID) AND the decider-layer SealKeyCollisionError (mapped to 422
by federation routes); 400 surfaces the decider-layer
InvalidSealFacilityIdError (whitespace-only facility_id slips past
Pydantic min_length=1); 403 surfaces Authorize-port denial; 409
surfaces the SealAlreadyExistsError singleton guard.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import SealAlreadyExistsError
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.aggregates.seal.state import InvalidSealFacilityIdError
from cora.federation.errors import UnauthorizedError
from cora.federation.features.initialize_seal.route import (
    _get_handler as _get_initialize_seal_handler,  # pyright: ignore[reportPrivateUsage]
)

_ONLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0a1"
_OFFLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0b1"


def _body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "facility_id": f"aps-2bm-{uuid4().hex[:8]}",
        "online_key_ref": _ONLINE_KEY_REF,
        "offline_key_ref": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_federation_seals_returns_201_with_stream_id_and_facility_id() -> None:
    body = _body()
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=body)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert "seal_stream_id" in payload
    assert "facility_id" in payload
    assert payload["facility_id"] == body["facility_id"]
    assert UUID(payload["seal_stream_id"]) == seal_stream_id(body["facility_id"])


@pytest.mark.contract
def test_post_federation_seals_rejects_missing_required_body_field_with_422() -> None:
    """facility_id missing -> Pydantic 422 before reaching the decider."""
    body = _body()
    del body["facility_id"]
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_rejects_missing_online_key_ref_with_422() -> None:
    body = _body()
    del body["online_key_ref"]
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_rejects_missing_offline_key_ref_with_422() -> None:
    body = _body()
    del body["offline_key_ref"]
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_rejects_empty_facility_id_with_422() -> None:
    """min_length=1 on facility_id rejects empty strings at Pydantic."""
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=_body(facility_id=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_rejects_malformed_uuid_with_422() -> None:
    """Pydantic rejects an online_key_ref that does not parse as UUID."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals",
            json=_body(online_key_ref="not-a-uuid"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_rejects_key_collision_with_422() -> None:
    """Decider-layer SealKeyCollisionError is routed to 422 by federation routes."""
    shared = "01900000-0000-7000-8000-00000000ccc1"
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals",
            json=_body(online_key_ref=shared, offline_key_ref=shared),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_extra_field_rejected_with_422() -> None:
    """`extra=forbid` rejects unknown body fields at Pydantic."""
    body = _body()
    body["unknown_field"] = "nope"
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_federation_seals_returns_409_on_already_exists() -> None:
    """SealAlreadyExistsError bubbles as 409 conflict."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise SealAlreadyExistsError("aps-2bm")

    app.dependency_overrides[_get_initialize_seal_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/seals", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_federation_seals_returns_400_on_whitespace_only_facility_id() -> None:
    """Whitespace-only facility_id slips past Pydantic min_length=1 and
    surfaces as 400 via the decider's InvalidSealFacilityIdError."""
    with TestClient(create_app()) as client:
        response = client.post("/federation/seals", json=_body(facility_id="   "))
    assert response.status_code == 400
    assert "facility_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_federation_seals_returns_400_when_handler_raises_invalid_facility_id() -> None:
    """An InvalidSealFacilityIdError from the handler maps to 400 (validation family)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise InvalidSealFacilityIdError("")

    app.dependency_overrides[_get_initialize_seal_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/seals", json=_body())
    assert response.status_code == 400
    assert "facility_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_federation_seals_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_initialize_seal_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/federation/seals", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
