"""Contract test for the health endpoint."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_health_returns_ok() -> None:
    """Use TestClient as a context manager so the FastAPI lifespan runs."""
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert response.headers.get("x-request-id") is not None
