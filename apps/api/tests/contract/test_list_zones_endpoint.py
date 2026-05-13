"""Contract tests for `GET /zones`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_zones_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/zones")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_zones_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/zones?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_zones_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/zones?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_zones_rejects_limit_below_min_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/zones?limit=0")
    assert response.status_code == 422
