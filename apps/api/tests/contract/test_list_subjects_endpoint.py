"""Contract tests for `GET /subjects`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_subjects_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/subjects")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize(
    "status_value",
    ["Received", "Mounted", "Measured", "Removed", "Returned", "Stored", "Discarded"],
)
def test_get_subjects_accepts_each_subject_status(client: TestClient, status_value: str) -> None:
    """Pin: every SubjectStatus enum value is accepted by the route's
    Literal validator."""
    with client:
        response = client.get(f"/subjects?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_subjects_rejects_unknown_status_with_422(client: TestClient) -> None:
    """Lowercase 'mounted' is NOT in the Literal (PascalCase per the
    BC-map vocabulary). Pydantic rejects."""
    with client:
        response = client.get("/subjects?status=mounted")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_subjects_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/subjects?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_subjects_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/subjects?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_subjects_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/subjects?limit=101")
    assert response.status_code == 422
