"""Contract tests for `GET /practices`."""

import uuid

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_practices_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/practices")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize("status_value", ["Defined", "Versioned", "Deprecated"])
def test_get_practices_accepts_each_status(client: TestClient, status_value: str) -> None:
    with client:
        response = client.get(f"/practices?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_practices_rejects_unknown_status_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/practices?status=defined")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_practices_rejects_invalid_method_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/practices?method_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_practices_combines_status_and_method_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/practices?status=Versioned&method_id={uuid.uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_practices_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/practices?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_practices_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/practices?limit=101")
    assert response.status_code == 422
