"""Contract tests for `GET /runs`."""

import uuid

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_runs_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/runs")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize(
    "status_value",
    ["Running", "Held", "Completed", "Aborted", "Stopped", "Truncated"],
)
def test_get_runs_accepts_each_status(client: TestClient, status_value: str) -> None:
    with client:
        response = client.get(f"/runs?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_runs_rejects_unknown_status_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/runs?status=running")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_runs_rejects_invalid_plan_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/runs?plan_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_runs_combines_status_and_plan_filter(client: TestClient) -> None:
    with client:
        response = client.get(f"/runs?status=Running&plan_id={uuid.uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_runs_accepts_campaign_id_filter(client: TestClient) -> None:
    """`?campaign_id=<uuid>` narrows to Runs that are members of the
    given Campaign."""
    with client:
        response = client.get(f"/runs?campaign_id={uuid.uuid4()}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_runs_rejects_invalid_campaign_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/runs?campaign_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_runs_combines_all_three_filters(client: TestClient) -> None:
    with client:
        response = client.get(
            f"/runs?status=Running&plan_id={uuid.uuid4()}&campaign_id={uuid.uuid4()}"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_runs_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/runs?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_runs_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/runs?limit=101")
    assert response.status_code == 422
