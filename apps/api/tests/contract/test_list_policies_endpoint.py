"""Contract tests for `GET /policies`."""

import uuid

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_policies_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/policies")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_policies_accepts_conduit_id_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/policies?conduit_id={uuid.uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_policies_rejects_invalid_conduit_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/policies?conduit_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_policies_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/policies?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_policies_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/policies?limit=101")
    assert response.status_code == 422
