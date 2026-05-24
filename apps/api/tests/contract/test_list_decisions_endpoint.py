"""Contract tests for `GET /decisions`."""

import uuid

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_decisions_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/decisions")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize("band", ["Low", "Medium", "High", "Certain"])
def test_get_decisions_accepts_each_confidence_band(client: TestClient, band: str) -> None:
    with client:
        response = client.get(f"/decisions?confidence_band={band}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_decisions_rejects_unknown_band_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/decisions?confidence_band=low")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_decisions_accepts_rule_filter(client: TestClient) -> None:
    with client:
        response = client.get("/decisions?rule=auto-accept")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_decisions_rejects_invalid_actor_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/decisions?actor_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_decisions_combines_all_filters(client: TestClient) -> None:
    with client:
        response = client.get(
            f"/decisions?confidence_band=Certain&rule=auto-accept&actor_id={uuid.uuid4()}"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_decisions_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/decisions?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_decisions_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/decisions?limit=101")
    assert response.status_code == 422
