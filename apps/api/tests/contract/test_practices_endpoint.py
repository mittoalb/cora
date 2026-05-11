"""Contract tests for `POST /practices`.

Mirror of `test_methods_endpoint.py`. Verifies request schema,
response schema, status codes, and that the whitespace-only-name
domain error maps to 400 via the BC's exception handler.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.recipe.aggregates.practice import (
    PRACTICE_NAME_MAX_LENGTH,
    PracticeAlreadyExistsError,
)
from cora.recipe.features.define_practice.route import (
    _get_handler as _get_define_practice_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_practices_returns_201_with_practice_id() -> None:
    method_id = str(uuid4())
    site_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={
                "name": "APS Standard Tomography",
                "method_id": method_id,
                "site_id": site_id,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert "practice_id" in body
    UUID(body["practice_id"])  # parses


@pytest.mark.contract
def test_post_practices_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={
                "name": "  APS Standard Tomography  ",
                "method_id": str(uuid4()),
                "site_id": str(uuid4()),
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_practices_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={"method_id": str(uuid4()), "site_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_practices_rejects_missing_method_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={"name": "X", "site_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_practices_rejects_missing_site_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={"name": "X", "method_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_practices_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={"name": "", "method_id": str(uuid4()), "site_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_practices_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={
                "name": "a" * 201,
                "method_id": str(uuid4()),
                "site_id": str(uuid4()),
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_practices_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={
                "name": "   ",
                "method_id": str(uuid4()),
                "site_id": str(uuid4()),
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_practices_rejects_non_uuid_method_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={"name": "X", "method_id": "not-a-uuid", "site_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_practices_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={
                "name": "a" * PRACTICE_NAME_MAX_LENGTH,
                "method_id": str(uuid4()),
                "site_id": str(uuid4()),
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_practices_accepts_refs_without_verifying_existence() -> None:
    """Eventual-consistency stance: bogus method_id and site_id are
    accepted at decide time. Mismatch surfaces at Plan binding (6e)."""
    bogus_method = "01900000-0000-7000-8000-deadbeefcafe"
    bogus_site = "01900000-0000-7000-8000-deadbeefcaff"
    with TestClient(create_app()) as client:
        response = client.post(
            "/practices",
            json={"name": "X", "method_id": bogus_method, "site_id": bogus_site},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_practices_returns_409_when_practice_already_exists() -> None:
    """Defensive guard: PracticeAlreadyExistsError -> 409. Stub the
    handler so the route's exception handler is verified end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise PracticeAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_define_practice_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/practices",
                json={"name": "X", "method_id": str(uuid4()), "site_id": str(uuid4())},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
