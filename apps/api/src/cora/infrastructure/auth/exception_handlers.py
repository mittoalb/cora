"""HTTP exception handlers for the Phase C edge-auth errors.

Two handlers are registered globally on the FastAPI app at startup
via `register_auth_exception_handlers(app)`:

  - `InvalidTokenError` -> HTTP 401 + RFC 6750 §3 WWW-Authenticate
    challenge. The `reason` short-string (e.g. "bad_signature",
    "expired", "wrong_audience") goes into the `error=` parameter
    of the challenge so clients can distinguish without parsing
    free-form text. The `error_description=` carries the (already
    operator-safe) `detail` field. Both values are quoted-string-
    escaped per RFC 7235 §2.2 to keep header parsers happy.
    Also includes `resource_metadata="<url>"` per RFC 9728 §4.1 so
    clients can discover where to acquire a fresh token.

  - `IntrospectionUnavailableError` -> HTTP 503 + `Retry-After: 5`.
    Distinct from the 401 path so operators can grep logs for
    "their token is bad" vs "our IdP introspection endpoint is
    down." The retry hint is conservative (5 seconds) so clients
    back off briefly rather than hammering the verifier during an
    upstream outage.

## Why a module-level register function

The BC convention: each BC's `register_<bc>_routes(app)` registers
its exception handlers. Auth errors are infrastructure-level (no
BC owns them), so they live in a parallel function called once at
app construction. Mirrors the `register_protected_resource_metadata_route`
shape next to it in main.py.

## Why not raise typed HTTPExceptions directly

The middleware (`BearerAuthMiddleware`) and the parser
(`_extract_bearer_token`) raise typed domain errors
(`InvalidTokenError`, `IntrospectionUnavailableError`) so:

  - The token verifier port stays HTTP-agnostic (it could be
    consumed by a future non-HTTP surface).
  - The error -> response mapping lives in one place per the BC
    handler convention.
  - Tests for the verifier + middleware can assert on typed errors
    without coupling to FastAPI's HTTPException internals.

Per RFC 6750 §3.1 the WWW-Authenticate header is REQUIRED on a 401
response that the resource server has authenticated as a bearer
challenge -- the BC convention's `JSONResponse(status_code=401)`
shape would omit this. So this module constructs the response
directly (not via `HTTPException`) to control headers.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import IntrospectionUnavailableError, InvalidTokenError

_log = get_logger(__name__)

# The "realm" parameter is REQUIRED in RFC 6750 §3 challenges. CORA
# is one realm; future multi-realm setups (multiple deployments
# behind a single gateway) override via a settings-driven helper.
_REALM = "cora"

# Per RFC 9728 §4.1, the WWW-Authenticate challenge MAY carry a
# `resource_metadata` parameter pointing at the protected-resource
# metadata document. CORA's lives at this fixed path (registered by
# `register_protected_resource_metadata_route`).
_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"


def _quote(value: str) -> str:
    """RFC 7235 §2.2 auth-param quoted-string: backslash-escape `"` and `\\`.

    Keeps WWW-Authenticate parsers happy when reason / detail strings
    contain shell-quote-eager characters. Values are operator-controlled
    (closed reason set + curated detail strings) so the escape surface
    is small, but the formal RFC compliance closes a class of header-
    injection-style edge cases at the boundary.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _bearer_challenge(*, error: str, error_description: str) -> str:
    """Format an RFC 6750 §3 Bearer challenge header value.

    Carries realm + error + error_description + resource_metadata.
    The order of auth-params is not significant per the RFC; the
    layout below matches the order clients most commonly grep for
    in failed-auth logs (error first).
    """
    parts = [
        f"Bearer realm={_quote(_REALM)}",
        f"error={_quote(error)}",
        f"error_description={_quote(error_description)}",
        f"resource_metadata={_quote(_RESOURCE_METADATA_PATH)}",
    ]
    return ", ".join(parts)


async def _handle_invalid_token(request: Request, exc: Exception) -> JSONResponse:
    """Map `InvalidTokenError` to HTTP 401 with RFC 6750 challenge."""
    # Pyright sees Exception in the FastAPI handler signature; the
    # registered class IS InvalidTokenError so the cast is safe.
    assert isinstance(exc, InvalidTokenError)  # type-narrow for pyright
    _log.info(
        "auth.invalid_token",
        path=request.url.path,
        method=request.method,
        reason=exc.reason,
    )
    # Per RFC 6750 §3.1, error_description SHOULD provide additional
    # detail. Use the curated `detail` field; fall back to the reason
    # short-string if detail is empty.
    description = exc.detail or exc.reason
    challenge = _bearer_challenge(error=exc.reason, error_description=description)
    return JSONResponse(
        status_code=401,
        content={"detail": description},
        headers={"WWW-Authenticate": challenge},
    )


async def _handle_introspection_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """Map `IntrospectionUnavailableError` to HTTP 503 + Retry-After."""
    assert isinstance(exc, IntrospectionUnavailableError)
    _log.warning(
        "auth.introspection_unavailable",
        path=request.url.path,
        method=request.method,
        issuer=exc.issuer,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                f"Token introspection endpoint for issuer {exc.issuer!r} "
                "is currently unavailable. Retry shortly."
            )
        },
        # `Retry-After: 5` is RFC 7231 §7.1.3 in delta-seconds form.
        # Five seconds is short enough to feel responsive once the IdP
        # is back, long enough that retries don't hammer the verifier.
        headers={"Retry-After": "5"},
    )


def register_auth_exception_handlers(app: FastAPI) -> None:
    """Register the auth-layer exception handlers on `app`.

    Idempotent in practice (FastAPI overrides on re-register). Called
    once at app construction in `cora.api.main.create_app`.

    Type system note: `add_exception_handler` is typed with
    `type[Exception]` keyed; the runtime IdpRegistry / middleware
    raises concrete subclasses that match.
    """
    # FastAPI's stub types `handler` as `(Request, Exception)` to be
    # the most general; concrete handlers narrow via assert internally.
    handler_invalid: Any = _handle_invalid_token
    handler_unavailable: Any = _handle_introspection_unavailable
    app.add_exception_handler(InvalidTokenError, handler_invalid)
    app.add_exception_handler(IntrospectionUnavailableError, handler_unavailable)


__all__ = ["register_auth_exception_handlers"]
