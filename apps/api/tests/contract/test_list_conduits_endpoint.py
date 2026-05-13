"""Contract tests for `GET /conduits`."""

import uuid

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_conduits_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/conduits")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_conduits_accepts_source_zone_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/conduits?source_zone_id={uuid.uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_conduits_accepts_target_zone_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/conduits?target_zone_id={uuid.uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_conduits_combines_both_endpoint_filters(client: TestClient) -> None:
    with client:
        response = client.get(
            f"/conduits?source_zone_id={uuid.uuid4()}&target_zone_id={uuid.uuid4()}"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_conduits_rejects_invalid_source_zone_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/conduits?source_zone_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_conduits_rejects_invalid_target_zone_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/conduits?target_zone_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_conduits_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/conduits?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_conduits_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/conduits?limit=101")
    assert response.status_code == 422
