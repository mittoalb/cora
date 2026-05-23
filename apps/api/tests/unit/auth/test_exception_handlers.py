"""Unit tests for the edge-auth exception handlers.

White-box pins for the response shape of the two registered
handlers: 401 + RFC 6750 WWW-Authenticate for `InvalidTokenError`,
503 + Retry-After for `IntrospectionUnavailableError`. The
contract-tier tests at `apps/api/tests/contract/test_bearer_auth_endpoints.py`
 drive the full request -> middleware -> handler -> response
chain against the real FastAPI app.
"""

# pyright: reportUnknownMemberType=false, reportPrivateUsage=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportAttributeAccessIssue=false

import json

import pytest
from starlette.applications import Starlette
from starlette.requests import Request

from cora.infrastructure.auth.exception_handlers import (
    _bearer_challenge,
    _handle_introspection_unavailable,
    _handle_invalid_token,
    _quote,
    register_auth_exception_handlers,
)
from cora.infrastructure.ports import IntrospectionUnavailableError, InvalidTokenError


def _fake_request(path: str = "/anywhere") -> Request:
    """Minimal Starlette Request for handler invocation in isolation."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "app": Starlette(),
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 0),
    }
    return Request(scope)


# ---------- _quote: RFC 7235 §2.2 ----------


@pytest.mark.unit
def test_quote_wraps_value_in_double_quotes() -> None:
    assert _quote("hello") == '"hello"'


@pytest.mark.unit
def test_quote_escapes_double_quote_and_backslash() -> None:
    """A reason / detail string with a `"` or `\\` would break the
    quoted-string per RFC 7235; escape them."""
    assert _quote('he said "hi"') == r'"he said \"hi\""'
    assert _quote(r"path\to\thing") == r'"path\\to\\thing"'


# ---------- _bearer_challenge: RFC 6750 §3 ----------


@pytest.mark.unit
def test_bearer_challenge_includes_all_required_params() -> None:
    """The challenge MUST carry realm + error + error_description +
    resource_metadata for clients to render meaningful errors and
    discover the protected-resource metadata endpoint."""
    challenge = _bearer_challenge(error="bad_signature", error_description="JWT signature failed")

    assert challenge.startswith("Bearer ")
    assert 'realm="cora"' in challenge
    assert 'error="bad_signature"' in challenge
    assert 'error_description="JWT signature failed"' in challenge
    assert 'resource_metadata="/.well-known/oauth-protected-resource"' in challenge


# ---------- _handle_invalid_token ----------


@pytest.mark.unit
async def test_handle_invalid_token_returns_401_with_www_authenticate() -> None:
    """Happy-path 401 shape: status code, JSON detail body, and the
    RFC 6750 challenge header.

    Gate-review SEC M2: response body + error_description carry ONLY
    the reason short-code; the free-form `detail` (which may include
    IdP-controlled subject / audience strings) stays in the log.
    """
    request = _fake_request("/actors")
    exc = InvalidTokenError("expired", "JWT exp 2026-01-01 in the past")

    response = await _handle_invalid_token(request, exc)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer ")
    assert 'error="expired"' in response.headers["WWW-Authenticate"]
    # error_description carries reason short-code only (no IdP detail).
    assert 'error_description="expired"' in response.headers["WWW-Authenticate"]
    body = json.loads(response.body)
    # Body carries reason only -- the IdP-controlled detail does not
    # leak to unauthenticated callers.
    assert body == {"detail": "expired"}


@pytest.mark.unit
async def test_handle_invalid_token_response_redacts_detail_even_when_present() -> None:
    """Gate-review SEC M2 pin: even with a populated detail, the
    response NEVER includes it. Prevents subject enumeration via
    `unknown_subject` and audience enumeration via `wrong_audience`.
    The detail still appears in the structlog line."""
    request = _fake_request("/actors")
    exc = InvalidTokenError(
        "unknown_subject",
        "no Actor mapped for issuer='https://idp.example.com' subject='target-user-abc'",
    )

    response = await _handle_invalid_token(request, exc)

    body = json.loads(response.body)
    assert body == {"detail": "unknown_subject"}
    # subject MUST NOT appear in the response body OR in any header.
    assert "target-user-abc" not in response.body.decode()
    assert "target-user-abc" not in str(response.headers)


@pytest.mark.unit
async def test_handle_invalid_token_falls_back_to_reason_when_detail_empty() -> None:
    """`detail=""` is permitted; the body MUST still carry a string,
    so the handler emits the reason short-code (which is also what
    populated `detail` would yield post-redaction)."""
    request = _fake_request("/actors")
    exc = InvalidTokenError("malformed", "")

    response = await _handle_invalid_token(request, exc)

    body = json.loads(response.body)
    assert body == {"detail": "malformed"}
    assert 'error_description="malformed"' in response.headers["WWW-Authenticate"]


@pytest.mark.unit
async def test_handle_invalid_token_escapes_quotes_in_reason() -> None:
    """If a reason somehow contains `"`, the header parser needs the
    backslash-escape per RFC 7235 §2.2."""
    request = _fake_request("/actors")
    # The closed reason set doesn't contain `"`, but a future addition
    # could; this pins the escape behavior at the boundary.
    exc = InvalidTokenError('weird"reason', "")

    response = await _handle_invalid_token(request, exc)

    challenge = response.headers["WWW-Authenticate"]
    assert r'error="weird\"reason"' in challenge
    assert r'error_description="weird\"reason"' in challenge


@pytest.mark.unit
async def test_handle_invalid_token_strips_crlf_in_reason() -> None:
    """Gate-review SEC M1: CR / LF / NUL / other CTLs in `reason`
    are STRIPPED by `_quote` so they cannot split the WWW-Authenticate
    header and inject another response header. Pin defensively even
    though today's closed reason set doesn't contain CTLs."""
    request = _fake_request("/actors")
    exc = InvalidTokenError("bad\r\nSet-Cookie: evil=1", "")

    response = await _handle_invalid_token(request, exc)

    challenge = response.headers["WWW-Authenticate"]
    # CR + LF replaced with single spaces; the injected Set-Cookie
    # appears as a header VALUE, not as a separate response header.
    assert "\r" not in challenge
    assert "\n" not in challenge
    # The challenge stays a valid single header value.
    assert challenge.startswith("Bearer ")


# ---------- _handle_introspection_unavailable ----------


@pytest.mark.unit
async def test_handle_introspection_unavailable_returns_503_with_retry_after() -> None:
    """503 + Retry-After: 5 per the design lock. Distinct status from
    401 so operators can grep logs for "their token bad" vs "our IdP
    down".

    Gate-review SEC M3: issuer URL MUST stay in the structured log
    only; response body emits a generic message to prevent
    unauthenticated attackers mapping which upstream IdP is degraded.
    """
    request = _fake_request("/actors")
    exc = IntrospectionUnavailableError("https://idp.example.com", "connection timeout")

    response = await _handle_introspection_unavailable(request, exc)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    body = json.loads(response.body)
    # Generic message: NO issuer URL, NO detail string.
    assert "unavailable" in body["detail"].lower()
    assert "https://idp.example.com" not in body["detail"]
    assert "connection timeout" not in body["detail"]


# ---------- register_auth_exception_handlers ----------


@pytest.mark.unit
def test_register_auth_exception_handlers_wires_both_classes() -> None:
    """Pin that BOTH error classes get a handler registered. Skipping
    one would leak a 500 instead of the typed 401/503."""
    from fastapi import FastAPI

    app = FastAPI()
    # Before registration: no handlers in the exception_handlers dict.
    assert InvalidTokenError not in app.exception_handlers
    assert IntrospectionUnavailableError not in app.exception_handlers

    register_auth_exception_handlers(app)

    assert InvalidTokenError in app.exception_handlers
    assert IntrospectionUnavailableError in app.exception_handlers
