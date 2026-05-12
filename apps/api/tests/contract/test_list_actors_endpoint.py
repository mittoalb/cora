"""Contract tests for `GET /actors`.

Pin: query-param shape, cursor pagination flow, status filter, error
paths (403 from authz, 422 from invalid cursor / out-of-range limit /
unknown status). These tests run with `app_env=test` and the in-
memory adapter so the endpoint returns empty pages — the focus is on
the request/response shape and error mapping, NOT the projection-
populated path (which is exercised in
`tests/integration/test_projection_worker_lifespan_postgres.py`).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_actors_returns_empty_page_with_no_data(client: TestClient) -> None:
    """Default response shape: 200 with empty items + null next_cursor.
    NOT 204 (RFC forbids body) and NOT 404 (collection exists).
    Pin: empty-result-as-200 is the modern REST convention."""
    with client:
        response = client.get("/actors")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_actors_accepts_status_filter(client: TestClient) -> None:
    """Status filter is `Literal["active", "deactivated"] | None`;
    omitting returns all (no magic 'all' value), explicit narrows."""
    with client:
        response = client.get("/actors?status=active")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_actors_rejects_unknown_status_with_422(
    client: TestClient,
) -> None:
    """Pydantic Literal validation catches unknown enum values."""
    with client:
        response = client.get("/actors?status=zombie")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_actors_accepts_limit_within_range(client: TestClient) -> None:
    with client:
        response = client.get("/actors?limit=10")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_actors_rejects_limit_zero_with_422(client: TestClient) -> None:
    """Limit must be >= 1; Field(ge=1) enforces."""
    with client:
        response = client.get("/actors?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_actors_rejects_limit_above_cap_with_422(
    client: TestClient,
) -> None:
    """Page size cap of 100 prevents server-side memory blowups."""
    with client:
        response = client.get("/actors?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_actors_rejects_invalid_cursor_with_422(
    client: TestClient,
) -> None:
    """Malformed cursor (corrupt base64 / missing separator / etc.)
    surfaces as `InvalidCursorError` at the handler and 422 via the
    Access exception handler."""
    with client:
        response = client.get("/actors?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_actors_accepts_traceparent_header_without_error(
    client: TestClient,
) -> None:
    """Pin: the W3C traceparent header is accepted without breaking
    the list endpoint. Full correlation-id propagation (header ->
    handler kwarg) is verified end-to-end for other endpoints in
    `test_principal_header.py`; here we just guard against the
    list endpoint regressing the header parsing."""
    with client:
        response = client.get(
            "/actors",
            headers={"traceparent": "00-12345678901234567890123456789012-1234567890123456-01"},
        )
    assert response.status_code == 200
