# pyright: reportPrivateUsage=false

"""Unit tests for `cora.infrastructure.auth.introspection_verifier`.

Uses pytest-httpserver to stand up an in-process IdP introspection
endpoint per test. Pins:

  - active token → VerifiedPrincipal
  - inactive token → InvalidTokenError(reason="introspection_inactive")
  - 5xx from IdP → IntrospectionUnavailableError
  - network failure → IntrospectionUnavailableError
  - 4xx from IdP → InvalidTokenError(reason="malformed")
  - response without `sub` → InvalidTokenError
  - audience mismatch (when IdP returns `aud`) → InvalidTokenError(reason="wrong_audience")
  - issuer mismatch (when IdP returns `iss`) → InvalidTokenError(reason="wrong_issuer")
  - per-token cache: second request within TTL hits cache, no second HTTP call
  - cache TTL expiry: second request after TTL elapses re-introspects
  - AH12: cache_ttl_seconds=0 rejected at construction
"""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import pytest
from pytest_httpserver import HTTPServer

from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.ports.token_verifier import (
    IntrospectionUnavailableError,
    InvalidTokenError,
    PrincipalKind,
)

_ISSUER = "https://test-globus.example.com"
_AUD_HTTP = "https://cora.test/http"
_SURFACE_HTTP = UUID("00000000-0000-0000-0000-000000000020")
_CLIENT_ID = "cora-rs"
_CLIENT_SECRET = "rs-secret"
_FIXED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000001")


def _make_mapper(
    *, kind: PrincipalKind = "human"
) -> Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]:
    async def mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        return (_FIXED_PRINCIPAL, kind)

    return mapper


def _make_verifier(introspection_url: str, *, cache_ttl_seconds: int = 30) -> IntrospectionVerifier:
    return IntrospectionVerifier(
        issuer=_ISSUER,
        introspection_url=introspection_url,
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        cache_ttl_seconds=cache_ttl_seconds,
        allow_insecure_introspection_url=True,
    )


@pytest.mark.unit
async def test_active_token_returns_verified_principal(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER, "aud": _AUD_HTTP}
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        principal = await verifier.verify("opaque-token-x", expected_audience=_SURFACE_HTTP)
        assert principal.principal_id == _FIXED_PRINCIPAL
        assert principal.subject == "user-abc"
        assert principal.issuer == _ISSUER
        assert principal.kind == "human"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_inactive_token_raises_invalid(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json({"active": False})
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("revoked", expected_audience=_SURFACE_HTTP)
        assert exc.value.reason == "introspection_inactive"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_idp_5xx_raises_unavailable(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_data(
        "internal error", status=500
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(IntrospectionUnavailableError) as exc:
            await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert exc.value.issuer == _ISSUER
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_network_failure_raises_unavailable() -> None:
    # Point at a non-routable port (Werkzeug not running).
    verifier = _make_verifier("http://127.0.0.1:1/introspect")
    try:
        with pytest.raises(IntrospectionUnavailableError):
            await verifier.verify("any", expected_audience=_SURFACE_HTTP)
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_idp_4xx_raises_invalid_malformed(
    httpserver: HTTPServer,
) -> None:
    """4xx from the IdP typically means CORA's introspection creds are
    wrong — surface as InvalidTokenError, not IntrospectionUnavailable
    (the upstream isn't 'down', the configuration is wrong)."""
    httpserver.expect_request("/introspect", method="POST").respond_with_data(
        "invalid_client", status=401
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert exc.value.reason == "malformed"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_missing_sub_claim_raises_invalid(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "iss": _ISSUER}  # missing 'sub'
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert exc.value.reason == "malformed"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_audience_mismatch_in_introspection_response(
    httpserver: HTTPServer,
) -> None:
    """When the IdP includes an `aud` field, it must match expected."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {
            "active": True,
            "sub": "user-abc",
            "iss": _ISSUER,
            "aud": "https://wrong-resource.example.com",
        }
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert exc.value.reason == "wrong_audience"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_audience_list_match_in_introspection_response(
    httpserver: HTTPServer,
) -> None:
    """`aud` can be a list (RFC 7662 §2.2); membership check, not equality."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {
            "active": True,
            "sub": "user-abc",
            "iss": _ISSUER,
            "aud": ["https://other.example.com", _AUD_HTTP],
        }
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        principal = await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert principal.subject == "user-abc"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_issuer_mismatch_raises_invalid(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {
            "active": True,
            "sub": "user-abc",
            "iss": "https://hostile-idp.example.com",
        }
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert exc.value.reason == "wrong_issuer"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_hit_avoids_second_http_call(
    httpserver: HTTPServer,
) -> None:
    """Two verifies of the same token within TTL → 1 HTTP call total."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=30)
    try:
        await verifier.verify("opaque-x", expected_audience=_SURFACE_HTTP)
        await verifier.verify("opaque-x", expected_audience=_SURFACE_HTTP)
        # Werkzeug records each request; expect exactly 1.
        assert len(httpserver.log) == 1
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_miss_when_token_differs(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        await verifier.verify("token-1", expected_audience=_SURFACE_HTTP)
        await verifier.verify("token-2", expected_audience=_SURFACE_HTTP)
        assert len(httpserver.log) == 2
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_expiry_triggers_refresh(
    httpserver: HTTPServer,
) -> None:
    """Wait past TTL → cache evicts → second verify re-introspects."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=1)
    try:
        await verifier.verify("opaque-x", expected_audience=_SURFACE_HTTP)
        await asyncio.sleep(1.1)
        await verifier.verify("opaque-x", expected_audience=_SURFACE_HTTP)
        assert len(httpserver.log) == 2
    finally:
        await verifier.aclose()


@pytest.mark.unit
def test_constructor_rejects_zero_cache_ttl() -> None:
    """AH12: no introspection without a per-token cache."""
    with pytest.raises(ValueError, match=r"cache_ttl_seconds|AH12"):
        IntrospectionVerifier(
            issuer=_ISSUER,
            introspection_url="https://example.com/introspect",
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
            subject_mapper=_make_mapper(),
            cache_ttl_seconds=0,
        )


@pytest.mark.unit
async def test_unconfigured_surface_rejected_before_idp_call(
    httpserver: HTTPServer,
) -> None:
    """expected_audience=Surface-not-in-config → InvalidTokenError
    (no IdP call made)."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json({"active": True})
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        unknown_surface = UUID("00000000-0000-0000-0000-000000000099")
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=unknown_surface)
        assert exc.value.reason == "wrong_audience"
        assert len(httpserver.log) == 0
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_basic_auth_credentials_sent_to_idp(
    httpserver: HTTPServer,
) -> None:
    """RFC 7662 §2.1: client_id + client_secret via HTTP Basic auth."""
    # pytest-httpserver lets us assert on request headers.
    import base64

    expected_basic = "Basic " + base64.b64encode(f"{_CLIENT_ID}:{_CLIENT_SECRET}".encode()).decode()
    httpserver.expect_request(
        "/introspect",
        method="POST",
        headers={"Authorization": expected_basic},
    ).respond_with_json({"active": True, "sub": "user-abc", "iss": _ISSUER})
    verifier = _make_verifier(httpserver.url_for("/introspect"))
    try:
        principal = await verifier.verify("any", expected_audience=_SURFACE_HTTP)
        assert principal.subject == "user-abc"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_injected_http_client_is_not_closed_by_verifier() -> None:
    """When the caller passes their own httpx.AsyncClient, the verifier
    must not close it on aclose() (the caller owns its lifetime)."""
    async with httpx.AsyncClient() as injected:
        verifier = IntrospectionVerifier(
            issuer=_ISSUER,
            introspection_url="http://127.0.0.1:1/introspect",
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
            subject_mapper=_make_mapper(),
            http_client=injected,
            allow_insecure_introspection_url=True,
        )
        await verifier.aclose()
        # Injected client must still be usable.
        assert not injected.is_closed


# ---------- gate-review fixes (BLOCKING F1 / F2 / F6 / F8 / impl#11) ----------


@pytest.mark.unit
async def test_cache_key_includes_audience_no_cross_surface_reuse(
    httpserver: HTTPServer,
) -> None:
    """BLOCKING gate-review F1: cache must be bound by `(token, aud)` so
    a token introspected for Surface A is NOT served from cache when
    presented for Surface B. The IdP MUST be re-consulted because its
    per-Surface aud policy may differ.

    Without the fix, the second call returns a cached hit and the IdP
    is never asked to validate the new audience."""
    surf_mcp = UUID("00000000-0000-0000-0000-000000000022")
    aud_mcp = "https://cora.test/mcp"

    # IdP returns active for HTTP aud; SAME token for MCP aud returns
    # `wrong_audience` because the IdP only authorized it for HTTP.
    httpserver.expect_request(
        "/introspect",
        method="POST",
    ).respond_with_json(
        {
            "active": True,
            "sub": "user-abc",
            "iss": _ISSUER,
            "aud": _AUD_HTTP,  # IdP says token is for HTTP only
        }
    )
    verifier = IntrospectionVerifier(
        issuer=_ISSUER,
        introspection_url=httpserver.url_for("/introspect"),
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP, surf_mcp: aud_mcp},
        subject_mapper=_make_mapper(),
        allow_insecure_introspection_url=True,
    )
    try:
        # First call: HTTP surface succeeds.
        await verifier.verify("opaque-token", expected_audience=_SURFACE_HTTP)
        assert len(httpserver.log) == 1
        # Second call: MCP surface. Pre-fix: cache hit, silently returns
        # the HTTP-bound principal. Post-fix: cache miss (different key),
        # IdP returns same `aud=HTTP`, our audience check raises.
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("opaque-token", expected_audience=surf_mcp)
        assert exc.value.reason == "wrong_audience"
        # Must have re-consulted the IdP (2 calls total, not 1).
        assert len(httpserver.log) == 2
    finally:
        await verifier.aclose()


@pytest.mark.unit
def test_constructor_rejects_http_introspection_url_without_opt_in() -> None:
    """Gate-review F2: introspection over HTTP would leak
    client_secret via HTTP Basic to a MITM."""
    with pytest.raises(ValueError, match=r"introspection_url must be HTTPS"):
        IntrospectionVerifier(
            issuer=_ISSUER,
            introspection_url="http://example.com/introspect",
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
            subject_mapper=_make_mapper(),
        )


@pytest.mark.unit
def test_client_secret_not_in_repr() -> None:
    """Gate-review F6: client_secret wrapped in SecretStr; never appears
    in __repr__ / accidental log dumps / traceback chain."""
    verifier = IntrospectionVerifier(
        issuer=_ISSUER,
        introspection_url="http://127.0.0.1:1/introspect",
        client_id=_CLIENT_ID,
        client_secret="super-secret-value",
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        allow_insecure_introspection_url=True,
    )
    text = repr(vars(verifier))
    assert "super-secret-value" not in text
    assert "SecretStr" in text  # confirms wrap happened


@pytest.mark.unit
async def test_cache_expiry_capped_by_token_exp(
    httpserver: HTTPServer,
) -> None:
    """Gate-review F8: if the IdP returns an `exp` field, the cache
    must NOT outlive the token's actual expiry. A token that the IdP
    says expires in 1s should NOT be served from cache after that
    second, even if cache_ttl_seconds is 30."""
    import time as time_mod

    # Token expires 1 second from now (per the IdP's introspection response).
    soon_exp = time_mod.time() + 1
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER, "exp": soon_exp}
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=30)
    try:
        await verifier.verify("short-lived-token", expected_audience=_SURFACE_HTTP)
        assert len(httpserver.log) == 1
        # Wait past the token's exp.
        await asyncio.sleep(1.2)
        # Cache should NOT serve this — token's exp has past.
        await verifier.verify("short-lived-token", expected_audience=_SURFACE_HTTP)
        assert len(httpserver.log) == 2, "cache must not outlive the IdP-declared token exp"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_bounded_under_token_flood(
    httpserver: HTTPServer,
) -> None:
    """Gate-review impl#11: cache must be bounded under a flood of
    unique tokens; otherwise long-lived process leaks memory."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = _make_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=30)
    try:
        # Set the cache cap low for the test.
        from cora.infrastructure.auth import introspection_verifier as iv_module

        original_cap = iv_module._MAX_CACHE_ENTRIES
        iv_module._MAX_CACHE_ENTRIES = 5
        try:
            for i in range(20):
                await verifier.verify(f"token-{i}", expected_audience=_SURFACE_HTTP)
            # pyright: ignore[reportPrivateUsage]
            assert len(verifier._cache) <= 5  # type: ignore[attr-defined]
        finally:
            iv_module._MAX_CACHE_ENTRIES = original_cap
    finally:
        await verifier.aclose()
