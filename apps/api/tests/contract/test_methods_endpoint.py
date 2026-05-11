"""Contract tests for `POST /methods`.

Mirror of `test_capabilities_endpoint.py`. Verifies request schema,
response schema, status codes, and that the whitespace-only-name
domain error maps to 400 via the BC's exception handler.

Pinned: needs_capabilities is required (use [] for procedural
Methods); empty list accepted; non-list rejected as 422.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    MethodAlreadyExistsError,
)
from cora.recipe.features.define_method.route import (
    _get_handler as _get_define_method_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_methods_returns_201_with_method_id() -> None:
    cap1 = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "XRF Mapping", "needs_capabilities": [cap1]},
        )

    assert response.status_code == 201
    body = response.json()
    assert "method_id" in body
    UUID(body["method_id"])  # parses


@pytest.mark.contract
def test_post_methods_accepts_empty_needs_capabilities() -> None:
    """Procedural Methods (no equipment requirement)."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "Sample Cleaning", "needs_capabilities": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "  XRF Mapping  ", "needs_capabilities": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/methods", json={"needs_capabilities": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_missing_needs_capabilities_with_422() -> None:
    """needs_capabilities is required (no default at the API
    boundary); use [] explicitly for procedural Methods."""
    with TestClient(create_app()) as client:
        response = client.post("/methods", json={"name": "X"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/methods", json={"name": "", "needs_capabilities": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "a" * 201, "needs_capabilities": []},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "   ", "needs_capabilities": []},
        )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_methods_rejects_non_uuid_capability_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "X", "needs_capabilities": ["not-a-uuid"]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_uses_max_length_constant_from_domain() -> None:
    """Pydantic max_length must track the domain METHOD_NAME_MAX_LENGTH constant."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "a" * METHOD_NAME_MAX_LENGTH, "needs_capabilities": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_accepts_capability_ids_without_verifying_existence() -> None:
    """Eventual-consistency stance: bogus Capability ids are accepted
    at decide time. Mismatch surfaces at Plan binding (6e). Pinned
    to lock the no-verification contract end-to-end."""
    bogus_cap = "01900000-0000-7000-8000-deadbeefcafe"
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={"name": "X", "needs_capabilities": [bogus_cap]},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_returns_409_when_method_already_exists() -> None:
    """Defensive guard: MethodAlreadyExistsError -> 409. Same pattern
    as CapabilityAlreadyExistsError. Stub the handler so the route's
    exception handler is verified end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise MethodAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_define_method_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/methods",
                json={"name": "X", "needs_capabilities": []},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
