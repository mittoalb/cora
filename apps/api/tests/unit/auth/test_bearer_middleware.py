"""Unit tests for `BearerAuthMiddleware`.

Strategy: test the middleware in isolation against a tiny Starlette
app rather than the full FastAPI/CORA stack. This pins the
middleware's contract (skip-paths, header parsing, verifier
dispatch, request.state attachment, error propagation) without
needing real Settings / Kernel / projection worker / DB pool.

The contract-tier tests in
`apps/api/tests/contract/test_bearer_auth_endpoints.py`
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
from cora.infrastructure.routing import (
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
)

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
    ],
)
def test_unauthenticated_paths_skip_verification_even_with_bearer(path: str) -> None:
    """The middleware's skip-list MUST short-circuit before calling
    the verifier, even if the request carries a Bearer header. This
    prevents the verifier from being called against probes (health /
    metrics) and the unauthenticated OAuth discovery endpoint.

    `/mcp/*` is NOT on this list; MCP verification is covered by the
    audience-dispatch tests below.
    """
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = _client(verifier=verifier)

    response = client.get(path, headers={"Authorization": "Bearer would-be-rejected"})

    assert response.status_code == 200
    assert response.json()["principal_attached"] is False
    assert verifier.last_call is None


# ---------- MCP path audience dispatch ----------


@pytest.mark.unit
def test_mcp_path_is_verified_with_mcp_surface_audience() -> None:
    """`/mcp/anything` is no longer skipped; the middleware
    verifies the token against `SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID`,
    NOT the HTTP Surface. AH5 (no shared `aud` across Surfaces): a
    token issued for HTTP MUST NOT verify against the MCP Surface and
    vice versa."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)

    response = client.get(
        "/mcp/anything",
        headers={"Authorization": "Bearer good-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["principal_attached"] is True
    assert verifier.last_call == ("good-token", SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID)


@pytest.mark.unit
def test_mcp_root_path_also_uses_mcp_surface_audience() -> None:
    """`/mcp` (exact, no trailing slash) is the mount root; it MUST
    also bind to the MCP Surface audience, not the HTTP one."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    app = Starlette(routes=[Route("/mcp", _echo_principal_handler)])
    app.add_middleware(BearerAuthMiddleware)

    @dataclass
    class _StubKernel:
        token_verifier: TokenVerifier | None

    app.state.deps = _StubKernel(token_verifier=verifier)
    client = TestClient(app)

    response = client.get("/mcp", headers={"Authorization": "Bearer good"})

    assert response.status_code == 200
    assert verifier.last_call == ("good", SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID)


@pytest.mark.unit
def test_mcp_path_invalid_token_returns_401() -> None:
    """A bad bearer on an MCP path returns the same 401 + RFC 6750
    WWW-Authenticate challenge as a bad bearer on an HTTP path. The
    response shape is symmetric across transports."""
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = _client(verifier=verifier)

    response = client.get(
        "/mcp/anything",
        headers={"Authorization": "Bearer bad"},
    )

    assert response.status_code == 401
    assert 'error="bad_signature"' in response.headers.get("WWW-Authenticate", "")
    assert verifier.last_call == ("bad", SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID)


@pytest.mark.unit
def test_mcp_prefix_fake_path_uses_http_surface_audience() -> None:
    """`/mcp-fake/admin` and similar paths that share the `/mcp` prefix
    but are NOT the MCP mount MUST bind to the HTTP Surface audience.
    Only `/mcp` exact + `/mcp/` prefix route to the MCP Surface."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    app = Starlette(routes=[Route("/mcp-fake/admin", _echo_principal_handler)])
    app.add_middleware(BearerAuthMiddleware)

    @dataclass
    class _StubKernel:
        token_verifier: TokenVerifier | None

    app.state.deps = _StubKernel(token_verifier=verifier)
    client = TestClient(app)

    response = client.get(
        "/mcp-fake/admin",
        headers={"Authorization": "Bearer good"},
    )

    assert response.status_code == 200
    assert verifier.last_call == ("good", SYSTEM_HTTP_SURFACE_ID)


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
    """Middleware passes through when no Authorization header is present on a non-/mcp path.

    Verifier configured + no Authorization header on a NON-/mcp path:
    middleware does NOT raise 401; that decision belongs to
    `get_principal_id` (which consults `require_authenticated_principal`).
    Pins the layering: middleware verifies WHEN a bearer is presented;
    the route layer decides WHETHER a bearer is required. (The rule
    holds for non-MCP paths; `/mcp/*` gets explicit middleware
    enforcement -- see below -- because FastMCP has no per-route
    Depends seam.)
    """
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = _client(verifier=verifier)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["principal_attached"] is False
    assert verifier.last_call is None


@pytest.mark.unit
def test_mcp_path_without_bearer_returns_401_with_challenge() -> None:
    """Under bearer-auth mode, /mcp paths MUST 401 at the
    middleware on a missing Authorization header. FastMCP's framing
    methods (initialize / tools/list / notifications/*) don't reach
    tool-handler code where `get_mcp_principal_id(ctx)` would raise,
    so without middleware-side enforcement they'd flow through
    unauthenticated. Mirrors the per-route `Depends(get_principal_id)`
    enforcement REST gets for free."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)

    response = client.get("/mcp/anything")

    assert response.status_code == 401
    challenge = response.headers.get("WWW-Authenticate", "")
    assert challenge.startswith("Bearer ")
    assert "/.well-known/oauth-protected-resource" in challenge
    # Verifier MUST NOT be called -- no token to verify.
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
def test_authorization_header_without_bearer_scheme_returns_401() -> None:
    """`Basic <creds>` or `Digest <creds>` are not bearer; reject so
    a misconfigured client doesn't silently flow as unauthenticated.
    BearerAuthMiddleware catches InvalidTokenError(reason=malformed)
    inline (Starlette BaseHTTPMiddleware doesn't route exceptions
    through the app's registered handler chain) and returns 401 with
    the RFC 6750 WWW-Authenticate challenge."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)

    response = client.get("/", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401
    assert 'error="malformed"' in response.headers.get("WWW-Authenticate", "")
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
def test_empty_or_missing_bearer_token_returns_401(header_value: str) -> None:
    """An `Authorization: Bearer` with no token value is not a valid
    presented credential; mapped to 401 with error=malformed."""
    verifier = _FakeTokenVerifier(verify_call=_always_succeed)
    client = _client(verifier=verifier)
    response = client.get("/", headers={"Authorization": header_value})
    assert response.status_code == 401
    assert 'error="malformed"' in response.headers.get("WWW-Authenticate", "")
    assert verifier.last_call is None


# ---------- Verifier failure conversion ----------


@pytest.mark.unit
def test_invalid_token_error_converted_to_401() -> None:
    """Middleware catches InvalidTokenError inline (BaseHTTPMiddleware
    quirk -- it can't propagate to FastAPI's add_exception_handler
    chain) and converts via `handle_invalid_token` to 401 with the
    reason short-code in the `error=` of the WWW-Authenticate
    challenge."""
    verifier = _FakeTokenVerifier(verify_call=_always_invalid)
    client = _client(verifier=verifier)
    response = client.get("/", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401
    assert 'error="bad_signature"' in response.headers.get("WWW-Authenticate", "")
    assert verifier.last_call == ("bad", SYSTEM_HTTP_SURFACE_ID)


@pytest.mark.unit
def test_introspection_unavailable_error_converted_to_503() -> None:
    """Upstream-down case: middleware converts to 503 + Retry-After: 5,
    distinct from the 401 token-bad path so operators can separate
    them in logs / dashboards."""
    verifier = _FakeTokenVerifier(verify_call=_always_unavailable)
    client = _client(verifier=verifier)
    response = client.get("/", headers={"Authorization": "Bearer x"})
    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "5"
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
