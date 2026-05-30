"""Contract tests for `GET /federation/seals`.

Pins the wire shape: query-param validation, response envelope, and
authorize-port denial wiring. Pagination + filter pass-through against
a real projection is covered at the integration tier.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.errors import UnauthorizedError
from cora.federation.features.list_seals.route import (
    _get_handler as _get_list_seals_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_get_federation_seals_returns_empty_page_when_projection_empty() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    with TestClient(create_app()) as client:
        response = client.get("/federation/seals")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_federation_seals_accepts_status_live_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/seals", params={"status": "Live"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_federation_seals_accepts_status_republishing_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/seals", params={"status": "Republishing"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_federation_seals_accepts_cursor_and_limit() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/federation/seals",
            params={"status": "Live", "limit": "25"},
        )
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_federation_seals_rejects_invalid_status_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/seals", params={"status": "Mystery"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_seals_rejects_limit_above_cap_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/seals", params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_seals_rejects_limit_below_one_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/seals", params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_seals_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> Any:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_list_seals_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get("/federation/seals")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
