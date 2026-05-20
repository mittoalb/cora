"""Unit tests for `BearerAuthMiddleware`.

Strategy: test the middleware in isolation against a tiny Starlette
app rather than the full FastAPI/CORA stack. This pins the
middleware's contract (skip-paths, header parsing, verifier
dispatch, request.state attachment, error propagation) without
needing real Settings / Kernel / projection worker / DB pool.

The contract-tier tests in
`apps/api/tests/contract/test_bearer_auth_endpoints.py` (Iter C-7)
cover the full request -> middleware -> handler -> response cycle
under real FastAPI app composition.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from cora.infrastructure.auth.bearer_middleware import BearerAuthMiddleware
from cora.infrastructure.ports import (
    IntrospectionUnavailableError,
    InvalidTokenError,
    TokenVerifier,
    VerifiedPrincipal,
)
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID

_ISSUER = "https://idp.example.com"
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000a01")


# ---------- Stub TokenVerifier ----------


@dataclass
class _FakeTokenVerifier:
    """Programmable verifier for middleware tests.

    `verify_call` is set by each test to the behavior under test:
    return a VerifiedPrincipal, raise InvalidTokenError, raise
    IntrospectionUnavailableError, etc. The instance also records
    the last (token, expected_audience) pair so tests can assert on
    what the middleware passed through.
    """

    verify_call: Callable[[str, UUID], Awaitable[VerifiedPrincipal]]
    last_call: tuple[str, UUID] | None = None

    async def verify(self, token: str, *, expected_audience: UUID) -> VerifiedPrincipal:
        self.last_call = (token, expected_audience)
        return await self.verify_call(token, expected_audience)


async def _always_succeed(_token: str, _audience: UUID) -> VerifiedPrincipal:
    return VerifiedPrincipal(
        principal_id=_PRINCIPAL_ID,
        subject="user-abc",
        issuer=_ISSUER,
        kind="human",
    )


async def _always_invalid(_token: str, _audience: UUID) -> VerifiedPrincipal:
    raise InvalidTokenError("bad_signature", "stub denied")


async def _always_unavailable(_token: str, _audience: UUID) -> VerifiedPrincipal:
    raise IntrospectionUnavailableError(_ISSUER, "stub upstream down")


# ---------- Test app ----------


async def _echo_principal_handler(request: Request) -> JSONResponse:
    """Test route that reports whether middleware attached a principal."""
    principal = getattr(request.state, "principal", None)
    if principal is None:
        return JSONResponse({"principal_attached": False})
    return JSONResponse(
        {
            "principal_attached": True,
            "principal_id": str(principal.principal_id),
            "issuer": principal.issuer,
        }
    )


def _build_app(*, verifier: TokenVerifier | None) -> Starlette:
    """Tiny Starlette app with the bearer middleware in front of a
    single echo route. Mimics the real `request.app.state.deps`
    surface the middleware reads from."""

    @dataclass
    class _StubKernel:
        token_verifier: TokenVerifier | None

    app = Starlette(
        routes=[
            Route("/", _echo_principal_handler),
            Route("/health", _echo_principal_handler),
            Route("/metrics", _echo_principal_handler),
            Route(
                "/.well-known/oauth-protected-resource",
                _echo_principal_handler,
            ),
            Route("/mcp/anything", _echo_principal_handler),
        ]
    )
    app.add_middleware(BearerAuthMiddleware)
    app.state.deps = _StubKernel(token_verifier=verifier)
    return app


def _client(*, verifier: TokenVerifier | None) -> TestClient:
    return TestClient(_build_app(verifier=verifier))


# ---------- Skip-path coverage ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/metrics",
        "/.well-known/oauth-protected-resource",
        "/mcp/anything",
    ],
)
def test_unauthenticated_paths_skip_verification_even_with_bearer(path: str) -> None:
    """The middleware's skip-list MUST short-circuit before calling
    the verifier, even if the request carries a Bearer header. This
    prevents the verifier from being called against probes (health /
    metrics) and the unauthenticated OAuth discovery endpoint."""
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = _client(verifier=verifier)

    response = client.get(path, headers={"Authorization": "Bearer would-be-rejected"})

    assert response.status_code == 200
    assert response.json()["principal_attached"] is False
    assert verifier.last_call is None


@pytest.mark.unit
def test_mcp_root_path_is_also_skipped() -> None:
    """`/mcp` (exact) and `/mcp/...` (prefix) both skip per Iter C-6
    deferral. The exact match guards the bare mount root."""
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    app = Starlette(routes=[Route("/mcp", _echo_principal_handler)])
    app.add_middleware(BearerAuthMiddleware)

    @dataclass
    class _StubKernel:
        token_verifier: TokenVerifier | None

    app.state.deps = _StubKernel(token_verifier=verifier)
    client = TestClient(app)

    response = client.get("/mcp", headers={"Authorization": "Bearer x"})
    assert response.status_code == 200


# ---------- No-verifier short-circuit ----------


@pytest.mark.unit
def test_no_verifier_configured_skips_extraction() -> None:
    """When `kernel.token_verifier is None` (no IdPs configured),
    middleware no-ops even if a Bearer header is present. The
    request flows to get_principal_id which uses the legacy
    X-Principal-Id-with-SYSTEM-fallback shape."""
    client = _client(verifier=None)

    response = client.get("/", headers={"Authorization": "Bearer ignored"})

    assert response.status_code == 200
    assert response.json()["principal_attached"] is False


# ---------- No-header pass-through ----------


@pytest.mark.unit
def test_no_authorization_header_passes_through_without_verify() -> None:
    """Verifier configured + no Authorization header: middleware does
    NOT raise 401; that decision belongs to get_principal_id (which
    consults `require_authenticated_principal`). Pins the layering:
    middleware verifies WHEN a bearer is presented; the route layer
    decides WHETHER a bearer is required."""
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = _client(verifier=verifier)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["principal_attached"] is False
    assert verifier.last_call is None


# ---------- Happy path ----------


@pytest.mark.unit
def test_valid_bearer_attaches_verified_principal_to_request_state() -> None:
    """The happy path. Middleware passes the token + arrival surface
    UUID to verifier.verify(); on success it stashes the
    VerifiedPrincipal on request.state.principal."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)

    response = client.get("/", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["principal_attached"] is True
    assert body["principal_id"] == str(_PRINCIPAL_ID)
    assert body["issuer"] == _ISSUER
    # Surface binding pin: middleware MUST pass the HTTP surface UUID.
    assert verifier.last_call == ("good-token", SYSTEM_HTTP_SURFACE_ID)


@pytest.mark.unit
def test_bearer_scheme_is_case_insensitive_per_rfc6750() -> None:
    """RFC 6750 §2.1 scheme is case-insensitive. Accept `bearer`, `BEARER`,
    `BeArEr` — common in clients that uppercase HTTP headers."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)

    for header in ("bearer good", "BEARER good", "BeArEr good"):
        response = client.get("/", headers={"Authorization": header})
        assert response.status_code == 200, header
        assert response.json()["principal_attached"] is True


# ---------- Malformed Authorization header ----------


@pytest.mark.unit
def test_authorization_header_without_bearer_scheme_raises_invalid_token() -> None:
    """`Basic <creds>` or `Digest <creds>` are not bearer; reject so
    a misconfigured client doesn't silently flow as unauthenticated.
    The middleware raises InvalidTokenError with reason=malformed;
    the exception handler (Iter C-4) converts to 401."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)

    # `raise_server_exceptions=False` lets TestClient return the 500
    # Starlette generates by default (no exception_handler registered
    # at the unit-test app level) rather than re-raising in the test
    # process. Iter C-7 contract tests pin the actual 401 behavior.
    client = TestClient(_build_app(verifier=verifier), raise_server_exceptions=False)
    response = client.get("/", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 500  # no handler -> Starlette default
    # Verifier MUST NOT be called for a malformed header.
    assert verifier.last_call is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "header_value",
    [
        "Bearer",  # no token
        "Bearer ",  # empty token
        "Bearer  ",  # whitespace-only token
    ],
)
def test_empty_or_missing_bearer_token_raises_invalid_token(header_value: str) -> None:
    """An `Authorization: Bearer` with no token value is not a valid
    presented credential; mapped to InvalidTokenError(malformed)."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = TestClient(_build_app(verifier=verifier), raise_server_exceptions=False)
    response = client.get("/", headers={"Authorization": header_value})
    assert response.status_code == 500  # propagates without Iter C-4 handler
    assert verifier.last_call is None


# ---------- Verifier failure propagation ----------


@pytest.mark.unit
def test_invalid_token_error_propagates_unchanged() -> None:
    """Middleware does NOT swallow InvalidTokenError. The route-layer
    exception handler (Iter C-4) catches it and emits 401 + the
    RFC 6750 WWW-Authenticate header."""
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = TestClient(_build_app(verifier=verifier), raise_server_exceptions=False)
    response = client.get("/", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 500  # no handler at unit-app level
    assert verifier.last_call == ("bad", SYSTEM_HTTP_SURFACE_ID)


@pytest.mark.unit
def test_introspection_unavailable_error_propagates_unchanged() -> None:
    """Same shape for the upstream-down case. Iter C-4 handler emits
    503 + Retry-After; middleware just propagates."""
    verifier = _FakeTokenVerifier(verify_call=_always_unavailable)
    client = TestClient(_build_app(verifier=verifier), raise_server_exceptions=False)
    response = client.get("/", headers={"Authorization": "Bearer x"})
    assert response.status_code == 500
    assert verifier.last_call == ("x", SYSTEM_HTTP_SURFACE_ID)


# ---------- Defensive: missing deps on app.state ----------


@pytest.mark.unit
def test_no_deps_on_app_state_short_circuits_safely() -> None:
    """If a request somehow arrives before lifespan attaches `deps`
    (Starlette holds requests, so this is defensive), middleware
    no-ops rather than crashing. The route layer's get_principal_id
    will then 500 cleanly when it can't read settings — not the
    middleware's job to detect."""
    app = Starlette(routes=[Route("/", _echo_principal_handler)])
    app.add_middleware(BearerAuthMiddleware)
    # NO app.state.deps set.

    client = TestClient(app)
    response = client.get("/", headers={"Authorization": "Bearer x"})
    assert response.status_code == 200


# ---------- Direct-extract helper coverage ----------


@pytest.mark.unit
def test_extract_bearer_token_rejects_non_bearer_scheme() -> None:
    """White-box: the parser's negative paths must all map to a
    typed InvalidTokenError(reason=malformed), not bare ValueError."""
    from cora.infrastructure.auth.bearer_middleware import _extract_bearer_token

    for header in (
        "Basic abcdef",
        "Digest username=foo",
        "Bearer\tx",  # tab instead of space — split tolerates
        "",
        "Bearer",
    ):
        if header == "Bearer\tx":
            # split() with no maxsplit splits on any whitespace; the
            # parser uses maxsplit=1 with default whitespace and so
            # tolerates this case. Pin the tolerated branch.
            assert _extract_bearer_token(header) == "x"
            continue
        with pytest.raises(InvalidTokenError, match="malformed"):
            _extract_bearer_token(header)


@pytest.mark.unit
def test_extract_bearer_token_preserves_token_with_internal_dots_and_dashes() -> None:
    """JWTs are dot-separated base64url; verifying the parser leaves
    them untouched."""
    from cora.infrastructure.auth.bearer_middleware import _extract_bearer_token

    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.signature-with-dashes"
    assert _extract_bearer_token(f"Bearer {jwt}") == jwt


def _unused_assert(_x: Any) -> None:
    """Pyright-quiet stub to keep imports used."""
    return None


_unused_assert(_FakeTokenVerifier)
