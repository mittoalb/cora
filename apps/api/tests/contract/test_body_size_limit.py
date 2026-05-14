"""Contract tests for the body-size limit middleware.

The middleware checks the inbound `Content-Length` header against
`Settings.max_request_body_size_bytes` and rejects with HTTP 413
before the request reaches any route. Tests bookend a small,
explicit limit to prove the middleware fires at the boundary.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.api.middleware import BodySizeLimitMiddleware


def _padded_name(target_total_body_bytes: int) -> str:
    """Build a name that pads the JSON body to (about) the target byte count.

    The JSON envelope `{"name": ""}` is 11 bytes; the name fills the rest.
    Returned padding is approximate but stable enough for over/under tests
    that bookend the configured limit by a wide margin.
    """
    envelope_overhead = 11
    return "x" * max(1, target_total_body_bytes - envelope_overhead)


@pytest.mark.contract
def test_post_under_limit_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body well under the configured limit reaches the route."""
    monkeypatch.setenv("MAX_REQUEST_BODY_SIZE_BYTES", "200")
    with TestClient(create_app()) as client:
        # Body roughly 50 bytes — well under 200.
        response = client.post("/actors", json={"name": _padded_name(50)})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_over_limit_returns_413(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body whose Content-Length exceeds the limit is rejected with 413."""
    monkeypatch.setenv("MAX_REQUEST_BODY_SIZE_BYTES", "100")
    with TestClient(create_app()) as client:
        # Body easily over 100.
        response = client.post("/actors", json={"name": _padded_name(500)})

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


@pytest.mark.contract
async def test_malformed_content_length_falls_through_to_inner_app() -> None:
    """Content-Length that isn't an integer (e.g. `notanumber`) is
    treated as length 0 and the request continues to the inner app —
    Starlette will then return 400 for the actual malformed-header
    condition. Hits the `int(raw_length)` ValueError fallback that
    every well-behaved HTTP client makes unreachable.

    Direct ASGI invocation: TestClient/httpx normalize Content-Length
    before transport, so the malformed bytes only land if we drive
    the middleware directly."""
    inner_called = False

    async def inner_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        _ = (scope, receive, send)
        nonlocal inner_called
        inner_called = True

    middleware = BodySizeLimitMiddleware(inner_app, max_bytes=1024)
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/anywhere",
        "headers": [(b"content-length", b"notanumber")],
    }

    async def _receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(_msg: dict[str, Any]) -> None:
        return None

    await middleware(scope, _receive, _send)
    assert inner_called is True, "Malformed Content-Length should not 413; it falls through."
