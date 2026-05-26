"""TokenVerifier port — edge auth.

Validates an inbound `Authorization: Bearer <token>` against a
configured identity provider and resolves the calling principal.

`TokenVerifier` is the hexagonal port; two adapters implement it:

  - `JwtTokenVerifier`     — local JWKS-based JWT verify (RFC 9068).
                        Industry IdPs that issue JWTs (Microsoft Entra,
                        Google, Auth0, Okta, AWS Cognito, Helmholtz
                        AAI, ORCID-via-OIDC) plug into this path.
  - `IntrospectionTokenVerifier` — RFC 7662 token introspection. Required
                        for Globus Auth (opaque-by-default) and any
                        future IdP that doesn't issue JWTs. Also the
                        revocation-strong path for cases where a
                        compromised JWT must be invalidated before
                        its `exp` ticks past.

Both adapters return the same `VerifiedPrincipal` shape so the
downstream call path (FastAPI middleware → `request.state.principal`
→ `get_principal_id` resolver → handler.authorize) is verifier-
agnostic.

## Adapter selection

The `IdentityProviderRegistry` (`cora.infrastructure.auth.idp_registry`)
owns the per-issuer adapter mapping at process startup. The HTTP/MCP
middleware does NOT make the adapter choice per request — it always
asks the registry, which routes by either:

  - JWT shape detection (3 dot-separated base64 chunks) + unverified
    `iss` claim peek → matching `JwtTokenVerifier`.
  - Otherwise → the deployment's configured `IntrospectionTokenVerifier`.

## Why a port, not a function

Two adapters is rule-of-two for a port today; rule-of-three would
trigger one. We're at two because:
  1. Test suites need a `TestTokenVerifier` for unit isolation
     (raises programmable outcomes without an IdP round-trip).
  2. Globus + non-Globus IdPs are operationally distinct paths.
The Protocol shape lets the kernel hold a `TokenVerifier` field
without leaking which adapter implementation; same architectural
move as `Authorize` (AllowAllAuthorize for tests / TrustAuthorize
for production).

## Errors

`InvalidTokenError` (→ HTTP 401 by the route layer) is the
catch-all for "the token failed verification" — bad signature,
expired, wrong audience, wrong issuer, malformed structure. Carries
a short machine-readable `reason` so logs distinguish modes without
leaking IdP details to the client.

`IntrospectionUnavailableError` (→ HTTP 503) is the introspection-
specific failure when the IdP can't be reached or returns 5xx. The
JWT path can't raise this (local verify, no network). Distinct from
`InvalidTokenError` so operators distinguish "your token is bad"
from "our upstream is down."

## What is NOT here

- The Authorize port stays unchanged — it already takes
  `principal_id: UUID`. `TokenVerifier.verify` returns the principal,
  Authorize gates the call.
- No session / cookie / CSRF concerns — CORA is stateless bearer.
- No OAuth client flows — CORA is a Resource Server (RS); the
  client obtains the token from the IdP and brings it. WI11 captures
  the trigger for revisiting OAuth-client capability.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

PrincipalKind = Literal["human", "service_account"]
"""Closed StrEnum-style discriminator. Aligned with `Actor.kind` in
the Access BC; the three values are `human`, `agent`, and
`service_account` (see Decision 9 of the edge-auth design lock)."""


SubjectMapper = Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]
"""Resolve `(issuer, subject)` → `(principal_id, kind)`.

The Access BC owns the IdP-subject → Actor.id mapping (the
`actor_idp_bindings` projection). Verifiers call this after token
verification and surface the result on `VerifiedPrincipal`.

Defined here on the port (not on each adapter) so the registry +
both adapters import a single canonical alias.

Failure modes the adapter wraps:
  - Mapper raises (unknown subject, projection lookup error, etc.) →
    `InvalidTokenError("unknown_subject", str(exc))`.
  - Mapper returns `principal_id == UUID(int=0)` (NIL_SENTINEL_ID) →
    `InvalidTokenError("unknown_subject", "subject mapped to nil sentinel")`.
  - Mapper returns `kind` not in the `PrincipalKind` closed set →
    `InvalidTokenError("malformed", "subject mapper returned invalid kind")`.
"""


@dataclass(frozen=True)
class VerifiedPrincipal:
    """The outcome of a successful `TokenVerifier.verify` call.

    `principal_id` is the UUID the downstream Authorize port keys on.
    Comes from the verifier's mapping of the token's `sub` claim to
    a registered `Actor.id` (the IdP-`sub`-to-Actor mapping lives in
    the Access BC; the verifier just returns the matched `principal_id`).

    `subject` is the raw `sub` claim string from the token, kept for
    forensics + structlog. Distinct from `principal_id` because
    operators may want to grep logs by IdP subject without joining
    against the Actor projection.

    `issuer` is the verified `iss` claim — which IdP minted this
    token. Forensic + per-IdP rate-limiting / metrics.

    `kind` discriminates human vs service-account callers, derived
    from the token's claims at issuance time (for example `aud` per-Surface
    + `client_credentials` grant → `service_account`).

    `scopes` carries the token's OAuth scopes if any (RFC 6749 §3.3).
    Empty `frozenset()` is fine — edge-auth ships without scope-aware
    authorization (scope→capability mapping is WI6).
    """

    principal_id: UUID
    subject: str
    issuer: str
    kind: PrincipalKind
    scopes: frozenset[str] = frozenset()


class InvalidTokenError(Exception):
    """The presented token failed verification.

    Mapped to HTTP 401 + `WWW-Authenticate: Bearer error="invalid_token"`
    (RFC 6750 §3.1) by the route-layer exception handler. The
    `reason` short string distinguishes modes for logs without
    leaking IdP details to the client response body.

    Reason codes (closed set, expand if a new verifier path needs):
      - "bad_signature"       — JWT signature verify failed
      - "expired"             — `exp` claim past
      - "not_yet_valid"       — `nbf` claim future
      - "wrong_audience"      — `aud` doesn't match expected Surface
      - "wrong_issuer"        — `iss` not in registered IdPs
      - "malformed"           — token structure unparseable
      - "unknown_subject"     — `sub` claim doesn't map to a known Actor
      - "introspection_inactive"  — RFC 7662 returned `active=false`
      - "unsupported_algorithm"   — JWT `alg` not in whitelist
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class IntrospectionUnavailableError(Exception):
    """The IdP's introspection endpoint couldn't be reached or returned 5xx.

    Mapped to HTTP 503 + `Retry-After: 5` by the route-layer exception
    handler. Distinct from `InvalidTokenError` so operators can
    distinguish "your token is bad" from "our upstream is down" in
    logs + dashboards.

    Only the `IntrospectionTokenVerifier` adapter raises this; the JWT
    path is fully local once the JWKS is cached.
    """

    def __init__(self, issuer: str, detail: str = "") -> None:
        super().__init__(
            f"Introspection endpoint for issuer {issuer!r} unavailable"
            + (f": {detail}" if detail else "")
        )
        self.issuer = issuer
        self.detail = detail


class TokenVerifier(Protocol):
    """Verify an `Authorization: Bearer <token>` value against a configured IdP.

    Implementations: `JwtTokenVerifier` (PyJWT + PyJWKClient), `IntrospectionTokenVerifier`
    (httpx + LRU cache), `TestTokenVerifier` (programmable, test-only).

    Per Decision 4 of the design lock: `expected_audience` is the
    resolved Surface UUID from `get_surface_id` / `get_mcp_surface_id`.
    The verifier looks up the configured audience string for that
    Surface and asserts `token.aud` matches. RFC 8707 §3 +
    RFC 9068 §4 — multi-audience tokens cross trust boundaries, so
    each Surface gets its own `aud`.
    """

    async def verify(
        self,
        token: str,
        *,
        expected_audience: UUID,
    ) -> VerifiedPrincipal:
        """Return the verified principal, or raise on failure.

        Failure modes: `InvalidTokenError` (bad token) or
        `IntrospectionUnavailableError` (IdP unreachable).
        `token` is the raw bearer value (without the `Bearer ` prefix).
        `expected_audience` is the Surface UUID the request arrived on.
        """
        ...


__all__ = [
    "IntrospectionUnavailableError",
    "InvalidTokenError",
    "PrincipalKind",
    "SubjectMapper",
    "TokenVerifier",
    "VerifiedPrincipal",
]
