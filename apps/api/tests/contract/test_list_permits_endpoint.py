"""Contract tests for `GET /federation/permits`.

Pins the wire shape: query-param validation, response envelope,
and authorize-port denial wiring. Pagination + filter pass-through
against a real projection is covered at the integration tier.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.errors import UnauthorizedError
from cora.federation.features.list_permits.route import (
    _get_handler as _get_list_permits_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_get_federation_permits_returns_empty_page_when_projection_empty() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_federation_permits_accepts_direction_outbound_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"direction": "Outbound"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_federation_permits_accepts_direction_inbound_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"direction": "Inbound"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_federation_permits_accepts_status_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"status": "Active"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_federation_permits_accepts_peer_facility_code_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/federation/permits",
            params={"peer_facility_code": "aps-2bm"},
        )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_federation_permits_accepts_full_filter_set() -> None:
    """All 3 filters + cursor / limit at once should parse cleanly."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/federation/permits",
            params={
                "direction": "Outbound",
                "status": "Suspended",
                "peer_facility_code": "aps-2bm",
                "limit": "25",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_federation_permits_rejects_invalid_direction_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"direction": "Sideways"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_permits_rejects_invalid_status_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"status": "Pending"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_permits_rejects_limit_above_cap_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_permits_rejects_limit_below_one_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits", params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_permits_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> Any:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_list_permits_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get("/federation/permits")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_get_federation_permits_does_not_surface_peer_facility_uuid_field() -> None:
    """peer_facility_code is an opaque external string; should not need to be UUID."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/federation/permits",
            params={"peer_facility_code": str(uuid4())},
        )
    assert response.status_code == 200
