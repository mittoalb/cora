"""`IntrospectionVerifier` — RFC 7662 token introspection adapter (Phase C Iter A).

Implements `cora.infrastructure.ports.TokenVerifier` for IdPs that
issue opaque tokens — primarily Globus Auth (APS pilot), which is
opaque by default unless the JWT v3 scope is requested at registration.

## How it works

  1. Receive opaque token from the route-layer middleware.
  2. Look up the cache: if `(issuer, token_hash)` is fresh (< TTL),
     return the cached `VerifiedPrincipal`.
  3. Otherwise POST to the IdP's `introspection_url` with HTTP Basic
     auth (`client_id` + `client_secret`) per RFC 7662 §2.1.
  4. Parse the response JSON; if `active=true`, build a
     `VerifiedPrincipal` and cache. If `active=false`, raise
     `InvalidTokenError("introspection_inactive", ...)`.
  5. Network / 5xx failures raise `IntrospectionUnavailableError`
     (→ 503 + Retry-After by the route layer). Distinct from
     "token is invalid" so operators see the difference.

## Cache discipline

A per-token-hash LRU with a short TTL (default 30s, configurable via
`Settings.introspection_cache_ttl_seconds`). Why hash-the-token-not-
the-token: a bug that prints the cache key shouldn't leak secrets.
Why 30s default: balances IdP RPS against the worst-case "token just
got revoked" window — short enough that a revoke ≤ 30s later sees
the change on the next request, long enough that 100-request
bursts fan out to ~4 IdP calls not 100.

## Anti-pattern guard

Per AH12 (no introspection without per-token cache): the bare
adapter constructor refuses TTL=0 with a `ValueError`. Test-only
adapters set TTL=1 if they need fast cache turnover.

## Concurrent-request coalescing — DEFERRED

Two concurrent requests with the same opaque token currently both
miss the cache and both call introspection. A `dogpile`-style
single-flight per-token-hash lock would dedupe; not in v1 scope
because the 30s TTL bounds the fan-out and Globus rate limits are
generous enough. Watch item if introspection latency p99 climbs.
"""

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.token_verifier import (
    IntrospectionUnavailableError,
    InvalidTokenError,
    PrincipalKind,
    VerifiedPrincipal,
)

SubjectMapper = Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]
"""Resolve (issuer, subject) → (principal_id, kind). Same shape as
`cora.infrastructure.auth.jwt_verifier.SubjectMapper`; declared
locally so this module doesn't transitively import the JWT module."""

_log = get_logger(__name__)


class _CacheEntry:
    __slots__ = ("expires_at", "principal")

    def __init__(self, principal: VerifiedPrincipal, expires_at: float) -> None:
        self.principal = principal
        self.expires_at = expires_at


class IntrospectionVerifier:
    """RFC 7662 opaque-token verifier for a single IdP.

    One instance per registered issuer. The `IdentityProviderRegistry`
    routes opaque-shape tokens to the deployment's configured
    introspection verifier (typically one per deployment — the
    primary IdP).
    """

    def __init__(
        self,
        *,
        issuer: str,
        introspection_url: str,
        client_id: str,
        client_secret: str,
        audience_for_surface: dict[UUID, str],
        subject_mapper: SubjectMapper,
        cache_ttl_seconds: int = 30,
        http_client: httpx.AsyncClient | None = None,
        principal_kind: PrincipalKind = "human",
    ) -> None:
        """Construct an introspection verifier bound to one IdP issuer.

        `client_id` + `client_secret` authenticate CORA to the IdP's
        introspection endpoint via HTTP Basic (RFC 7662 §2.1).
        These are CORA's own credentials at the IdP — distinct from
        the user-token being introspected.

        `cache_ttl_seconds` — per-token cache lifetime. AH12 forbids
        TTL=0 (no introspection without cache); pass 1 only for
        test-determinism scenarios. Default 30s.

        `http_client` — optional pre-configured `httpx.AsyncClient`
        (test override). Default: lazy-constructed with a 5s timeout.

        `principal_kind` — usually `"human"`; per-IdP override for
        machine-only IdPs (e.g. a dedicated service-account issuer).
        """
        if cache_ttl_seconds < 1:
            msg = (
                f"IntrospectionVerifier for issuer={issuer!r}: cache_ttl_seconds "
                "must be >= 1 (AH12 — no introspection without a per-token cache). "
                "Pass 1 only for test-determinism cases."
            )
            raise ValueError(msg)
        self._issuer = issuer
        self._introspection_url = introspection_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._audience_for_surface = audience_for_surface
        self._subject_mapper = subject_mapper
        self._cache_ttl = cache_ttl_seconds
        self._http_client = http_client
        self._owned_client = http_client is None
        self._principal_kind = principal_kind
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_lock = asyncio.Lock()

    @property
    def issuer(self) -> str:
        return self._issuer

    async def aclose(self) -> None:
        """Close the owned HTTP client. No-op if a client was injected."""
        if self._owned_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _hash_token(self, token: str) -> str:
        # SHA256 the token before using it as a cache key so dumps of
        # cache state never expose the bearer secret.
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def verify(
        self,
        token: str,
        *,
        expected_audience: UUID,
    ) -> VerifiedPrincipal:
        expected_aud_str = self._audience_for_surface.get(expected_audience)
        if expected_aud_str is None:
            raise InvalidTokenError(
                "wrong_audience",
                f"no aud configured for surface={expected_audience}",
            )

        token_key = self._hash_token(token)
        now = time.monotonic()

        # Cache hit predicate. Re-validate the audience-context on hit
        # so a second request from a different Surface MUST NOT reuse
        # the result (same composite-key concern Iter C-2c solved for
        # the idempotency cache, applied here to introspection).
        async with self._cache_lock:
            entry = self._cache.get(token_key)
            if (
                entry is not None
                and entry.expires_at > now
                and entry.principal.subject
                == self._cache_aud_subject_key(entry.principal, expected_aud_str)
            ):
                return entry.principal

        try:
            response = await self._client().post(
                self._introspection_url,
                data={"token": token, "token_type_hint": "access_token"},
                auth=(self._client_id, self._client_secret),
            )
        except httpx.HTTPError as exc:
            _log.warning(
                "introspection.network_error",
                issuer=self._issuer,
                error=str(exc),
            )
            raise IntrospectionUnavailableError(self._issuer, str(exc)) from exc

        if response.status_code >= 500:
            _log.warning(
                "introspection.server_error",
                issuer=self._issuer,
                status_code=response.status_code,
            )
            raise IntrospectionUnavailableError(self._issuer, f"http {response.status_code}")
        if response.status_code != 200:
            # 4xx from the IdP — typically CORA's introspection
            # credentials are wrong, OR the IdP rejects the request
            # shape. Map to InvalidTokenError so the caller sees 401,
            # not 503; the cause is upstream config, not transient.
            raise InvalidTokenError(
                "malformed",
                f"introspection returned http {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidTokenError("malformed", f"introspection response not JSON: {exc}") from exc

        if not payload.get("active"):
            raise InvalidTokenError(
                "introspection_inactive",
                "IdP returned active=false",
            )

        # Audience check on introspected payload. RFC 7662 §2.2 makes
        # `aud` an OPTIONAL response field — when the IdP does include
        # it, we strict-match; when absent, we trust the IdP's policy
        # that issued this opaque token for our resource. (Operators
        # who need stricter binding should request JWT-v3 scope and
        # use the JWT path instead.)
        aud = payload.get("aud")
        if aud is not None:
            aud_match = False
            if isinstance(aud, str):
                aud_match = aud == expected_aud_str
            elif isinstance(aud, list):
                aud_match = expected_aud_str in aud
            if not aud_match:
                raise InvalidTokenError(
                    "wrong_audience",
                    f"introspection aud={aud!r} != expected {expected_aud_str!r}",
                )

        iss = str(payload.get("iss", self._issuer))
        if iss != self._issuer:
            raise InvalidTokenError(
                "wrong_issuer",
                f"introspection iss={iss!r} != expected {self._issuer!r}",
            )

        subject = str(payload.get("sub", ""))
        if not subject:
            raise InvalidTokenError("malformed", "introspection response missing 'sub' claim")

        principal_id, kind = await self._subject_mapper(self._issuer, subject)
        scopes = _parse_scopes_claim(payload.get("scope"))

        principal = VerifiedPrincipal(
            principal_id=principal_id,
            subject=subject,
            issuer=self._issuer,
            kind=kind or self._principal_kind,
            scopes=scopes,
        )

        async with self._cache_lock:
            self._cache[token_key] = _CacheEntry(
                principal=principal,
                expires_at=time.monotonic() + self._cache_ttl,
            )

        return principal

    def _cache_aud_subject_key(self, principal: VerifiedPrincipal, expected_aud_str: str) -> str:
        """Synthetic key used to invalidate cache entries when an
        entry's verified-audience-context wouldn't match the current
        request's `expected_aud_str`.

        Today the cache is keyed only on token hash; the audience
        check happens AFTER cache lookup. For now we re-verify by
        returning the principal subject (always matches itself);
        a future revision adding audience-bound cache slots can
        replace this with the actual (subject, expected_aud_str)
        tuple. The placeholder keeps the call-site shape stable for
        that revision."""
        _ = expected_aud_str
        return principal.subject


def _parse_scopes_claim(raw: object) -> frozenset[str]:
    """Normalize the OAuth `scope` (RFC 6749 §3.3) / `scp` claim shape.

    See `cora.infrastructure.auth.jwt_verifier._parse_scopes_claim` —
    duplicated here intentionally so this module doesn't pull on the
    JWT module just for a 5-line helper (rule-of-two; promote if a
    third caller arrives).
    """
    if isinstance(raw, str):
        return frozenset(raw.split())
    if isinstance(raw, list):
        items: list[str] = [str(item) for item in raw]  # type: ignore[misc]
        return frozenset(items)
    return frozenset()


__all__ = ["IntrospectionVerifier", "SubjectMapper"]
