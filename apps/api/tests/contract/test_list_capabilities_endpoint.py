"""Contract tests for `GET /families`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_capabilities_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/families")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize("status_value", ["Defined", "Versioned", "Deprecated"])
def test_get_capabilities_accepts_each_status(client: TestClient, status_value: str) -> None:
    with client:
        response = client.get(f"/families?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_capabilities_rejects_unknown_status_with_422(client: TestClient) -> None:
    """lowercase 'defined' is NOT in the Literal."""
    with client:
        response = client.get("/families?status=defined")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_capabilities_rejects_invalid_cursor_with_422(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/families?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_capabilities_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/families?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_capabilities_rejects_limit_above_cap_with_422(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/families?limit=101")
    assert response.status_code == 422
