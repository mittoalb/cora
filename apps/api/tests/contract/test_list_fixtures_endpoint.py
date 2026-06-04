"""Contract tests for `GET /fixtures`.

TestClient has no Postgres pool, so contract tests verify shape and
param validation only. Actual data round-trips live in the
integration suite (test_list_fixtures_handler_postgres.py).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_fixtures_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/fixtures")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_fixtures_accepts_assembly_id_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/fixtures?assembly_id={uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_fixtures_accepts_surface_id_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/fixtures?surface_id={uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_fixtures_accepts_assembly_content_hash_filter(client: TestClient) -> None:
    with client:
        response = client.get("/fixtures?assembly_content_hash=" + "a" * 64)
    assert response.status_code == 200


@pytest.mark.contract
def test_get_fixtures_accepts_all_filters_combined(client: TestClient) -> None:
    with client:
        response = client.get(
            f"/fixtures?assembly_id={uuid4()}&surface_id={uuid4()}"
            f"&assembly_content_hash={'a' * 64}&limit=10"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_fixtures_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/fixtures?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_fixtures_rejects_limit_over_100_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/fixtures?limit=999")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_fixtures_rejects_invalid_assembly_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/fixtures?assembly_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_fixtures_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/fixtures?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422
