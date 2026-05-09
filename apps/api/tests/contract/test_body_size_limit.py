"""Contract tests for the body-size limit middleware.

The middleware checks the inbound `Content-Length` header against
`Settings.max_request_body_size_bytes` and rejects with HTTP 413
before the request reaches any route. Tests poke at /actors (the
existing POST endpoint) for both happy and rejection paths.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_under_limit_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_REQUEST_BODY_SIZE_BYTES", "1024")
    with TestClient(create_app()) as client:
        # Tiny body, well under 1024.
        response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_over_limit_returns_413(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body whose Content-Length exceeds the limit is rejected with 413."""
    monkeypatch.setenv("MAX_REQUEST_BODY_SIZE_BYTES", "100")
    with TestClient(create_app()) as client:
        # name padded out so the JSON body easily exceeds 100 bytes.
        response = client.post("/actors", json={"name": "x" * 200})

    assert response.status_code == 413
    body = response.json()
    assert "detail" in body
    assert "exceeds limit" in body["detail"].lower()


@pytest.mark.contract
def test_413_response_is_json_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """413 body shape matches the BC exception-handler convention
    `{"detail": str}` so clients see uniform error responses."""
    monkeypatch.setenv("MAX_REQUEST_BODY_SIZE_BYTES", "10")
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body.keys()) == {"detail"}
