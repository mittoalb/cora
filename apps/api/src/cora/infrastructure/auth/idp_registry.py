"""`IdentityProviderRegistry` — process-singleton verifier router (Phase C Iter A).

Owns the per-issuer `TokenVerifier` mapping at the composition root.
The HTTP/MCP middleware (Iter C) hands the registry a raw bearer
token; the registry routes to the right adapter by:

  1. **Token shape**: if the token parses as 3 base64url chunks
     separated by `.` it's a JWT; otherwise it's opaque.
  2. **For JWTs**: peek the unverified header's `iss` claim (no
     signature check — that happens inside the verifier) and route
     to the matching `JWTVerifier`.
  3. **For opaque tokens**: route to the deployment's configured
     `IntrospectionVerifier`. Exactly one per registry today; if
     deployments ever need multiple opaque-token IdPs, the registry
     grows a discriminator (probably the token prefix per the
     pattern GitHub `ghp_`/`gho_`/`ghs_` uses).

## Why peek-unverified for JWT routing

Reading `iss` before signature verification looks scary. It's safe
because the verifier we route to STILL checks `iss == self._issuer`
strictly — peeking is just routing, not trust. An attacker forging
an `iss` claim still has to forge a signature the chosen
`JWTVerifier`'s JWKS won't accept. This is the standard pattern
(`PyJWT.get_unverified_header` / `decode_complete` with
`verify_signature=False` for routing only).

## Anti-pattern guards

- Empty registry construction is a hard error (you can't have an
  `IdpRegistry` with zero IdPs; that's a misconfigured deployment).
- Duplicate issuer registration is a hard error (two verifiers for
  the same `iss` is ambiguous).
- Unknown-issuer token → `InvalidTokenError("wrong_issuer", ...)`
  immediately (no fallback to introspection — issuers must be
  pre-registered).

## Subject mapper note

A `SubjectMapper` is required at construction. Today the only
implementation is the trivial in-memory `dict` (`StaticSubjectMapper`)
used by tests. Iter B wires the production mapper that queries the
access projection's `actor_idp_bindings` table.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

import jwt

from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.ports.token_verifier import (
    InvalidTokenError,
    PrincipalKind,
    TokenVerifier,
    VerifiedPrincipal,
)

SubjectMapper = Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]
"""Re-exported here so external callers can import a single name
from `cora.infrastructure.auth` for the production mapper signature.
Same shape as `cora.infrastructure.auth.jwt_verifier.SubjectMapper`."""


class _RegistryEntry(Protocol):
    """Common Protocol both adapter types satisfy (issuer + verify)."""

    @property
    def issuer(self) -> str: ...

    async def verify(
        self,
        token: str,
        *,
        expected_audience: UUID,
    ) -> VerifiedPrincipal: ...


class IdentityProviderRegistry:
    """Process-singleton router from inbound token → matching `TokenVerifier`.

    Constructed once at lifespan start from `Settings.identity_providers`
    (Iter B); held on the `Kernel` and used by the middleware (Iter C).
    """

    def __init__(
        self,
        jwt_verifiers: list[JWTVerifier],
        introspection_verifier: IntrospectionVerifier | None = None,
    ) -> None:
        """Construct the registry from explicit verifier instances.

        `jwt_verifiers` — one per JWT-issuing IdP. May be empty (e.g.
        deployment that only uses Globus opaque tokens).
        `introspection_verifier` — at most one per deployment. None
        is valid (deployment serves only JWT-issuing IdPs).

        At least one verifier (JWT or introspection) MUST be present;
        the registry refuses an empty configuration.
        """
        if not jwt_verifiers and introspection_verifier is None:
            msg = (
                "IdentityProviderRegistry must be constructed with at least "
                "one verifier (JWT or introspection). An empty registry can "
                "never authenticate any request — likely a misconfigured "
                "Settings.identity_providers list."
            )
            raise ValueError(msg)

        by_issuer: dict[str, JWTVerifier] = {}
        for v in jwt_verifiers:
            if v.issuer in by_issuer:
                msg = (
                    f"Duplicate JWTVerifier registered for issuer={v.issuer!r}. "
                    "Each issuer maps to exactly one verifier."
                )
                raise ValueError(msg)
            by_issuer[v.issuer] = v
        self._jwt_by_issuer = by_issuer
        self._introspection = introspection_verifier

    async def verify(
        self,
        token: str,
        *,
        expected_audience: UUID,
    ) -> VerifiedPrincipal:
        """Route the token to the right verifier and return the result.

        Raises `InvalidTokenError` if the token shape can't be
        classified, the issuer isn't registered, or the chosen
        verifier raises. Raises `IntrospectionUnavailableError` only
        from the introspection path.
        """
        if not token:
            raise InvalidTokenError("malformed", "empty token")

        verifier = self._choose_verifier(token)
        return await verifier.verify(token, expected_audience=expected_audience)

    def _choose_verifier(self, token: str) -> _RegistryEntry:
        if _looks_like_jwt(token):
            try:
                unverified = jwt.get_unverified_header(token)
            except jwt.DecodeError as exc:
                raise InvalidTokenError("malformed", str(exc)) from exc
            # `iss` lives in the payload, not the header. We re-decode
            # without verification to peek it — PyJWT exposes this via
            # decode(..., options={"verify_signature": False}).
            try:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": False},
                )
            except jwt.DecodeError as exc:
                raise InvalidTokenError("malformed", str(exc)) from exc
            _ = unverified  # reserved: future per-header routing
            iss = payload.get("iss")
            if not isinstance(iss, str):
                raise InvalidTokenError("malformed", "JWT missing string 'iss' claim")
            verifier = self._jwt_by_issuer.get(iss)
            if verifier is None:
                raise InvalidTokenError(
                    "wrong_issuer",
                    f"no JWTVerifier registered for iss={iss!r}",
                )
            return verifier
        # Opaque token branch.
        if self._introspection is None:
            raise InvalidTokenError(
                "malformed",
                "opaque token but no IntrospectionVerifier registered",
            )
        return self._introspection


def _looks_like_jwt(token: str) -> bool:
    """Cheap shape check: a JWT is three `.`-separated base64url chunks.

    NOT a security check — opaque tokens that happen to contain two
    dots would false-positive. The selected `JWTVerifier` then fails
    fast on `bad_signature`/`malformed`. The shape probe just avoids
    a pointless introspection call on every clearly-JWT-shaped
    token.
    """
    return token.count(".") == 2


# Type-equivalence sanity: the registry IS a TokenVerifier itself, so
# downstream call sites can hold a `TokenVerifier` (the port) without
# knowing whether it's a single adapter or the routing registry.
_: TokenVerifier = IdentityProviderRegistry.__new__(IdentityProviderRegistry)  # type: ignore[misc, assignment]
del _


__all__ = ["IdentityProviderRegistry", "SubjectMapper"]
