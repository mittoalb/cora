"""Contract tests for `POST /subjects`.

Mirror of the other create-style endpoint tests. Verifies request
schema, response schema, status codes, and that the
whitespace-only-name domain error maps to 400 via the BC's
exception handler.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH, SubjectAlreadyExistsError
from cora.subject.features.register_subject.route import (
    _get_handler as _get_register_subject_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_subjects_returns_201_with_subject_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/subjects", json={"name": "Sample-A1"})

    assert response.status_code == 201
    body = response.json()
    assert "subject_id" in body
    UUID(body["subject_id"])  # parses without raising


@pytest.mark.contract
def test_post_subjects_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/subjects", json={"name": "  Sample-A1  "})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_subjects_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/subjects", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_subjects_rejects_empty_name_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        response = client.post("/subjects", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_subjects_rejects_too_long_name_with_422() -> None:
    """Pydantic max_length=200 catches over-length names."""
    with TestClient(create_app()) as client:
        response = client.post("/subjects", json={"name": "a" * 201})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_subjects_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/subjects", json={"name": "   "})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_subjects_uses_max_length_constant_from_domain() -> None:
    """Pydantic max_length must track the domain SUBJECT_NAME_MAX_LENGTH constant."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/subjects",
            json={"name": "a" * SUBJECT_NAME_MAX_LENGTH},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_subjects_returns_409_when_subject_already_exists() -> None:
    """Defensive guard: SubjectAlreadyExistsError -> 409.

    This decider raise is essentially impossible in production with
    UUIDv7 ids (would require an IdGenerator collision). The test
    overrides the slice handler with a stub that raises directly so
    the route's exception handler can be verified end-to-end. Pinned
    because without the registered handler, the raise would surface
    as 500 instead of a clean 409.
    """
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise SubjectAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_register_subject_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post("/subjects", json={"name": "Sample-A1"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
