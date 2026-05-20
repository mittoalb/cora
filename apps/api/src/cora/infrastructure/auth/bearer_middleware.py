"""HTTP middleware that verifies `Authorization: Bearer` tokens.

Sits between the inbound HTTP request and route dispatch. On every
request it:

  1. Skips paths that MUST be unauthenticated (health, metrics,
     RFC 9728 protected-resource metadata). These exist so external
     monitoring + OAuth clients can probe the deployment without
     credentials.
  2. Skips when no `TokenVerifier` is configured on the kernel
     (today's default: legacy `X-Principal-Id`-with-`SYSTEM`-fallback
     stays in effect — see `cora.infrastructure.routing.get_principal_id`).
  3. Skips when no `Authorization` header is present. The route-layer
     `get_principal_id` Depends decides whether to 401 based on
     `Settings.require_authenticated_principal`; the middleware does
     NOT impose its own policy.
  4. Parses the `Authorization` header for `Bearer <token>`; mangled
     shapes raise `InvalidTokenError("malformed", ...)`.
  5. Resolves the arrival Surface UUID (today: the single SYSTEM HTTP
     Surface; future: per-app-state lookup if multiple HTTP Surfaces
     ever ship) and calls
     `verifier.verify(token, expected_audience=surface_id)`.
  6. Stores the resulting `VerifiedPrincipal` on `request.state.principal`
     so the route-layer `get_principal_id` can read it without another
     verification call.

`InvalidTokenError` + `IntrospectionUnavailableError` propagate out of
the middleware and are converted to HTTP responses by the BC-style
exception handlers registered at app construction (Iter C-4 wires
`register_auth_exception_handlers(app)`).

## Why BaseHTTPMiddleware over raw ASGI

`BodySizeLimitMiddleware` uses raw ASGI because it must short-circuit
before any body is read — the receive() must NOT be called. Bearer
auth has no such constraint; it just needs the request scope. Using
Starlette's `BaseHTTPMiddleware` lets exceptions propagate cleanly
through FastAPI's registered exception handlers (the BC convention)
instead of constructing JSON responses inline.

## Why the path-skip list lives here, not in the route layer

Routes that need to be unauthenticated (health, metrics, .well-known)
don't have a single FastAPI-layer marker today (no `@unauthenticated`
decorator). Centralising the list here keeps the auth boundary
explicit and grep-able: one file lists every unauthenticated path.
If the project later adds a per-route marker, this list collapses to
"check the marker on the matched route" without touching this file's
shape.

## MCP path skip

`/mcp/...` is skipped here because FastMCP doesn't yet thread the
`Authorization` header through to tools (MCP spec 2025-11-25 supports
OAuth 2.1 but the python-sdk integration is still pending). Iter C-6
documents the gap; until 8f-d wires MCP edge-auth, MCP tools continue
to hardcode `SYSTEM_PRINCIPAL_ID` (mcp_gate.py refuses to register
write tools under `require_authenticated_principal=True` so the gap
is closed against accidental prod exposure).
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID

if TYPE_CHECKING:
    from cora.infrastructure.ports import TokenVerifier
# `InvalidTokenError` is RAISED at runtime so it can't be
# TYPE_CHECKING-gated; it's imported lazily inside the helper that
# raises it. The runtime path: middleware -> auth/__init__ ->
# bearer_middleware -> ports/__init__ -> port modules -> routing ->
# observability -> config (Settings) -> auth.config -> back into
# `cora.infrastructure.auth` which is mid-load. Pinning the
# `InvalidTokenError` import inside `_extract_bearer_token` breaks
# the cycle at module-init time without sacrificing the typed-error
# contract.

_log = get_logger(__name__)

# Paths the middleware MUST never authenticate. Health and metrics
# are unauthenticated by deployment convention (k8s probes, Prometheus
# scrape). `/.well-known/oauth-protected-resource` (RFC 9728) is
# unauthenticated by spec — clients discover where to get a token.
_UNAUTHENTICATED_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/metrics",
        "/.well-known/oauth-protected-resource",
    }
)


def _is_unauthenticated_path(path: str) -> bool:
    """Return True if `path` MUST be skipped by the bearer middleware.

    Exact-match for the three unauthenticated paths plus an
    `/mcp/` prefix check (Iter C-6 deferral; see module docstring).
    The prefix check is intentionally NOT applied to `/.well-known/`
    in general — only the single RFC 9728 path is allowed through.
    """
    if path in _UNAUTHENTICATED_PATHS:
        return True
    return path.startswith("/mcp/") or path == "/mcp"


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Verify `Authorization: Bearer <token>` against the kernel TokenVerifier.

    Stateless: every request reads `kernel.token_verifier` off
    `request.app.state.deps`. The verifier is process-singleton built
    once at lifespan start (Iter C-1); the middleware just dispatches.

    When `kernel.token_verifier is None` (no IdPs configured) the
    middleware no-ops and the legacy `X-Principal-Id` path takes over.
    This is the "edge-auth disabled" mode; flipping it on is one
    `IDENTITY_PROVIDERS=[...]` env var away.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if _is_unauthenticated_path(request.url.path):
            return await call_next(request)

        # `app.state.deps` is populated by the lifespan; the only path
        # where it could be unset is a request that hits before the
        # lifespan finishes. Starlette / FastAPI hold requests until
        # then so this is defensive — pyright doesn't know it.
        deps = getattr(request.app.state, "deps", None)
        verifier: TokenVerifier | None = deps.token_verifier if deps is not None else None
        if verifier is None:
            return await call_next(request)

        authorization = request.headers.get("authorization")
        if authorization is None:
            # No bearer presented; defer the 401-or-fallback decision
            # to get_principal_id which knows about
            # `require_authenticated_principal` + `app_env`.
            return await call_next(request)

        token = _extract_bearer_token(authorization)
        # Raises InvalidTokenError or IntrospectionUnavailableError
        # on failure -> propagated to exception handlers (Iter C-4).
        principal = await verifier.verify(
            token,
            expected_audience=SYSTEM_HTTP_SURFACE_ID,
        )
        # Stash on request.state so get_principal_id can pull it
        # without re-verifying. Per-request state; no cross-request
        # leakage even with worker reuse.
        request.state.principal = principal
        _log.debug(
            "bearer_auth.verified",
            path=request.url.path,
            principal_id=str(principal.principal_id),
            issuer=principal.issuer,
            kind=principal.kind,
        )
        return await call_next(request)


def _extract_bearer_token(authorization_header: str) -> str:
    """Parse `Bearer <token>` from an Authorization header value.

    RFC 6750 §2.1 specifies a single space between the scheme and
    the credentials, case-insensitive scheme. Tolerate extra
    whitespace; reject every other shape.
    """
    # Lazy import: see module-level note for the cycle this breaks.
    from cora.infrastructure.ports import InvalidTokenError

    parts = authorization_header.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenError(
            "malformed",
            "Authorization header is not a `Bearer <token>` shape",
        )
    token = parts[1].strip()
    if not token:
        raise InvalidTokenError(
            "malformed",
            "Authorization Bearer token value is empty",
        )
    return token


__all__ = ["BearerAuthMiddleware"]
