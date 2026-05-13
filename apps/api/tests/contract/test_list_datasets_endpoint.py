"""Contract tests for `GET /datasets`."""

import uuid

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_datasets_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/datasets")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize("status_value", ["Registered", "Discarded"])
def test_get_datasets_accepts_each_status(client: TestClient, status_value: str) -> None:
    with client:
        response = client.get(f"/datasets?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_datasets_rejects_unknown_status_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/datasets?status=registered")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_datasets_rejects_invalid_run_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/datasets?producing_run_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_datasets_rejects_invalid_subject_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/datasets?subject_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_datasets_combines_all_filters(client: TestClient) -> None:
    with client:
        response = client.get(
            f"/datasets?status=Registered&producing_run_id={uuid.uuid4()}&subject_id={uuid.uuid4()}"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_datasets_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/datasets?limit=101")
    assert response.status_code == 422
