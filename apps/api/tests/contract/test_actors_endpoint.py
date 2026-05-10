"""Contract tests for `POST /actors`.

Verifies the HTTP surface: request schema, response schema, status
codes, and that domain errors are translated to the right HTTP status.
The full lifespan runs (TestClient as a context manager), so the
in-memory event store is wired and the `app.state.access.register_actor`
handler is exercised end-to-end through FastAPI's DI graph.

Persistence semantics are covered by the unit + integration tests for
the handler; this test file does not re-verify what landed in the store.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH, ActorAlreadyExistsError
from cora.access.features.register_actor.route import (
    _get_handler as _get_register_actor_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.api.main import create_app


@pytest.mark.contract
def test_post_actors_returns_201_with_actor_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "Doga"})

    assert response.status_code == 201
    body = response.json()
    assert "actor_id" in body
    UUID(body["actor_id"])  # parses without raising


@pytest.mark.contract
def test_post_actors_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "  Doga  "})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_rejects_empty_name_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_rejects_too_long_name_with_422() -> None:
    """Pydantic max_length=200 catches over-length names."""
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "a" * 201})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "   "})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_actors_rejects_non_string_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": 123})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_actors_uses_max_length_constant_from_domain() -> None:
    """Pydantic max_length must track the domain ACTOR_NAME_MAX_LENGTH constant."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "a" * ACTOR_NAME_MAX_LENGTH},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_returns_409_when_actor_already_exists() -> None:
    """Defensive guard: ActorAlreadyExistsError -> 409.

    This decider raise is essentially impossible in production with
    UUIDv7 ids (would require an IdGenerator collision). The test
    overrides the slice handler with a stub that raises directly so
    the route's exception handler can be verified end-to-end. Pinned
    because without the registered handler, the raise would surface
    as 500 instead of a clean 409.
    """
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise ActorAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_register_actor_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post("/actors", json={"name": "Doga"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
