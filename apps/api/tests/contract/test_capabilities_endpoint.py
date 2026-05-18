"""Contract tests for `POST /families`.

Mirror of the other create-style endpoint tests. Verifies request
schema, response schema, status codes, and that the
whitespace-only-name domain error maps to 400 via the BC's
exception handler.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.family import (
    FAMILY_NAME_MAX_LENGTH,
    FamilyAlreadyExistsError,
)
from cora.equipment.features.define_family.route import (
    _get_handler as _get_define_family_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_capabilities_returns_201_with_family_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "Tomography", "affordances": []})

    assert response.status_code == 201
    body = response.json()
    assert "family_id" in body
    UUID(body["family_id"])  # parses


@pytest.mark.contract
def test_post_capabilities_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "  Tomography  ", "affordances": []})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_capabilities_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_capabilities_rejects_empty_name_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "", "affordances": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_capabilities_rejects_too_long_name_with_422() -> None:
    """Pydantic max_length=200 catches over-length names."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "a" * 201, "affordances": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_capabilities_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "   ", "affordances": []})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_capabilities_rejects_non_string_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": 123, "affordances": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_capabilities_uses_max_length_constant_from_domain() -> None:
    """Pydantic max_length must track the domain FAMILY_NAME_MAX_LENGTH constant."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/families",
            json={"name": "a" * FAMILY_NAME_MAX_LENGTH, "affordances": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_capabilities_returns_409_when_capability_already_exists() -> None:
    """Defensive guard: FamilyAlreadyExistsError -> 409. Same
    pattern as ActorAlreadyExistsError / SubjectAlreadyExistsError —
    essentially impossible in production with UUIDv7 ids, but the
    unmapped raise would surface as 500 instead of a clean 409.
    Test overrides the slice handler with a stub that raises
    directly so the route's exception handler is verified
    end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise FamilyAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_define_family_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post("/families", json={"name": "Tomography", "affordances": []})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
