"""Contract tests for `GET /supplies`.

End-to-end pagination/filter behavior against a real projection
lives in the integration suite. These tests pin the contract: empty
page when no data, status-code shape, parameter validation.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.supply.errors import UnauthorizedError
from cora.supply.features.list_supplies.handler import Handler as ListSuppliesHandler
from cora.supply.features.list_supplies.route import (
    _get_handler as _get_list_supplies_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_supplies_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/supplies")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize("scope_value", ["Facility", "Sector", "Beamline"])
def test_get_supplies_accepts_each_scope(client: TestClient, scope_value: str) -> None:
    with client:
        response = client.get(f"/supplies?scope={scope_value}")
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize(
    "status_value",
    ["Unknown", "Available", "Degraded", "Unavailable", "Recovering", "Decommissioned"],
)
def test_get_supplies_accepts_each_status_locked_day_one(
    client: TestClient, status_value: str
) -> None:
    """All 6 statuses accepted: 5 FSM health states locked at full enum
    width per project_supply_design (forward-compat), plus the lifecycle-
    terminal Decommissioned per project_deregister_supply_design. Callers
    filter explicitly when they want only-active or only-decommissioned;
    no default exclusion. Matches Asset and Subject sibling-BC convention."""
    with client:
        response = client.get(f"/supplies?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_supplies_accepts_kind_filter(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?kind=LiquidNitrogen")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_supplies_accepts_combined_filters(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?scope=Beamline&kind=LiquidNitrogen&status=Available")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_supplies_rejects_unknown_scope_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?scope=Galaxy")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supplies_rejects_unknown_status_with_422(client: TestClient) -> None:
    """Lowercase 'unknown' is NOT in the Literal."""
    with client:
        response = client.get("/supplies?status=unknown")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supplies_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supplies_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supplies_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supplies_rejects_empty_kind_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/supplies?kind=")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supplies_returns_403_when_authorize_denies() -> None:
    """Route documents 403 in `responses=`; this pins the wire-level path."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> ListSuppliesHandler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_list_supplies_handler] = _override
    with TestClient(app) as fastapi_client:
        response = fastapi_client.get("/supplies")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
