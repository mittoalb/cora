"""Contract tests for `POST /actors`.

Verifies the HTTP surface: request schema, response schema, status
codes, and that domain errors are translated to the right HTTP status.
The full lifespan runs (TestClient as a context manager), so the
in-memory event store is wired and the `app.state.access.register_actor`
handler is exercised end-to-end through FastAPI's DI graph.

Persistence semantics are covered by the unit + integration tests for
the handler; this test file does not re-verify what landed in the store.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import app


@pytest.mark.contract
def test_post_actors_returns_201_with_actor_id() -> None:
    with TestClient(app) as client:
        response = client.post("/actors", json={"name": "Doga"})

    assert response.status_code == 201
    body = response.json()
    assert "actor_id" in body
    UUID(body["actor_id"])  # parses without raising
    assert response.headers.get("x-request-id") is not None


@pytest.mark.contract
def test_post_actors_trims_whitespace_in_name() -> None:
    with TestClient(app) as client:
        response = client.post("/actors", json={"name": "  Doga  "})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_rejects_missing_name_with_422() -> None:
    with TestClient(app) as client:
        response = client.post("/actors", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_rejects_empty_name_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(app) as client:
        response = client.post("/actors", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_rejects_too_long_name_with_422() -> None:
    """Pydantic max_length=200 catches over-length names."""
    with TestClient(app) as client:
        response = client.post("/actors", json={"name": "a" * 201})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(app) as client:
        response = client.post("/actors", json={"name": "   "})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_actors_rejects_non_string_name_with_422() -> None:
    with TestClient(app) as client:
        response = client.post("/actors", json={"name": 123})
    assert response.status_code == 422
