# pyright: reportPrivateUsage=false

"""Unit tests for `cora.infrastructure.adapters.introspection_token_verifier`.

Uses pytest-httpserver to stand up an in-process IdP introspection
endpoint per test. Pins:

  - active token → VerifiedPrincipal
  - inactive token / 4xx / 5xx / network failure → distinct error classes
  - audience-list match (RFC 7662 §2.2)
  - issuer mismatch + missing-sub → InvalidTokenError
  - per-(token, aud) composite cache key (BLOCKING gate-review item)
  - cache TTL + exp-cap + LRU bound + opt-in for HTTP introspection URL
  - cache_ttl_seconds=0 rejected at construction
  - client_secret never appears in __repr__
  - concurrent-coalescing pin: two simultaneous requests with same
    token currently both miss (deferred single-flight per memo §2)
"""

import asyncio
from uuid import UUID

import httpx
import pytest
from pytest_httpserver import HTTPServer

from cora.infrastructure.adapters.introspection_token_verifier import IntrospectionTokenVerifier
from cora.infrastructure.ports.token_verifier import (
    IntrospectionUnavailableError,
    InvalidTokenError,
)
from tests.unit.auth._helpers import (
    FIXED_PRINCIPAL_ID,
    TEST_AUD_HTTP,
    TEST_CLIENT_ID,
    TEST_CLIENT_SECRET,
    TEST_SURFACE_HTTP,
    make_introspection_verifier,
    make_mapper,
)
from tests.unit.auth._helpers import (
    TEST_INTROSPECTION_ISSUER as _ISSUER,
)

# ---------- happy path + failure classes ----------


@pytest.mark.unit
async def test_active_token_returns_verified_principal(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER, "aud": TEST_AUD_HTTP}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        principal = await verifier.verify("opaque-x", expected_audience=TEST_SURFACE_HTTP)
        assert principal.principal_id == FIXED_PRINCIPAL_ID
        assert principal.subject == "user-abc"
        assert principal.issuer == _ISSUER
        assert principal.kind == "human"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_inactive_token_raises_invalid(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json({"active": False})
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("revoked", expected_audience=TEST_SURFACE_HTTP)
        assert exc.value.reason == "introspection_inactive"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_idp_5xx_raises_unavailable(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_data(
        "internal error", status=500
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(IntrospectionUnavailableError) as exc:
            await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert exc.value.issuer == _ISSUER
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_network_failure_raises_unavailable() -> None:
    verifier = make_introspection_verifier("http://127.0.0.1:1/introspect")
    try:
        with pytest.raises(IntrospectionUnavailableError):
            await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_idp_4xx_raises_invalid_malformed(httpserver: HTTPServer) -> None:
    """4xx → typically CORA's introspection creds are wrong → 401 not 503."""
    httpserver.expect_request("/introspect", method="POST").respond_with_data(
        "invalid_client", status=401
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert exc.value.reason == "malformed"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_missing_sub_claim_raises_invalid(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "iss": _ISSUER}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert exc.value.reason == "malformed"
    finally:
        await verifier.aclose()


# ---------- audience / issuer binding ----------


@pytest.mark.unit
async def test_audience_mismatch_in_introspection_response(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {
            "active": True,
            "sub": "user-abc",
            "iss": _ISSUER,
            "aud": "https://wrong-resource.example.com",
        }
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert exc.value.reason == "wrong_audience"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_audience_list_match_in_introspection_response(
    httpserver: HTTPServer,
) -> None:
    """RFC 7662 §2.2: `aud` may be a list — membership, not equality."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {
            "active": True,
            "sub": "user-abc",
            "iss": _ISSUER,
            "aud": ["https://other.example.com", TEST_AUD_HTTP],
        }
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        principal = await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert principal.subject == "user-abc"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_issuer_mismatch_raises_invalid(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": "https://hostile-idp.example.com"}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert exc.value.reason == "wrong_issuer"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_unconfigured_surface_rejected_before_idp_call(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json({"active": True})
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        unknown_surface = UUID("00000000-0000-0000-0000-000000000099")
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("any", expected_audience=unknown_surface)
        assert exc.value.reason == "wrong_audience"
        assert len(httpserver.log) == 0
    finally:
        await verifier.aclose()


# ---------- cache discipline ----------


@pytest.mark.unit
async def test_cache_hit_avoids_second_http_call(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=30)
    try:
        await verifier.verify("opaque-x", expected_audience=TEST_SURFACE_HTTP)
        await verifier.verify("opaque-x", expected_audience=TEST_SURFACE_HTTP)
        assert len(httpserver.log) == 1
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_miss_when_token_differs(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        await verifier.verify("token-1", expected_audience=TEST_SURFACE_HTTP)
        await verifier.verify("token-2", expected_audience=TEST_SURFACE_HTTP)
        assert len(httpserver.log) == 2
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_expiry_triggers_refresh(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=1)
    try:
        await verifier.verify("opaque-x", expected_audience=TEST_SURFACE_HTTP)
        await asyncio.sleep(1.1)
        await verifier.verify("opaque-x", expected_audience=TEST_SURFACE_HTTP)
        assert len(httpserver.log) == 2
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_key_includes_audience_no_cross_surface_reuse(
    httpserver: HTTPServer,
) -> None:
    """BLOCKING gate-review F1: cache must be bound by (token, aud) so
    a token introspected for Surface A is NOT served from cache when
    presented for Surface B. The IdP MUST be re-consulted because its
    per-Surface aud policy may differ."""
    surf_mcp = UUID("00000000-0000-0000-0000-000000000022")
    aud_mcp = "https://cora.test/mcp"
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER, "aud": TEST_AUD_HTTP}
    )
    verifier = IntrospectionTokenVerifier(
        issuer=_ISSUER,
        introspection_url=httpserver.url_for("/introspect"),
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP, surf_mcp: aud_mcp},
        subject_mapper=make_mapper(),
        allow_insecure_introspection_url=True,
    )
    try:
        await verifier.verify("opaque-token", expected_audience=TEST_SURFACE_HTTP)
        assert len(httpserver.log) == 1
        with pytest.raises(InvalidTokenError) as exc:
            await verifier.verify("opaque-token", expected_audience=surf_mcp)
        assert exc.value.reason == "wrong_audience"
        assert len(httpserver.log) == 2, "must re-consult IdP for different Surface"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_expiry_capped_by_token_exp(httpserver: HTTPServer) -> None:
    """Gate-review F8: cache TTL bounded by the IdP-declared `exp`."""
    import time as time_mod

    soon_exp = time_mod.time() + 1
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER, "exp": soon_exp}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=30)
    try:
        await verifier.verify("short-lived", expected_audience=TEST_SURFACE_HTTP)
        assert len(httpserver.log) == 1
        await asyncio.sleep(1.2)
        await verifier.verify("short-lived", expected_audience=TEST_SURFACE_HTTP)
        assert len(httpserver.log) == 2, "cache must not outlive token exp"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_cache_bounded_under_token_flood(httpserver: HTTPServer) -> None:
    """Gate-review impl#11: bounded cache size under unique-token flood."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"), cache_ttl_seconds=30)
    try:
        from cora.infrastructure.adapters import introspection_token_verifier as iv_module

        original_cap = iv_module._MAX_CACHE_ENTRIES
        iv_module._MAX_CACHE_ENTRIES = 5
        try:
            for i in range(20):
                await verifier.verify(f"token-{i}", expected_audience=TEST_SURFACE_HTTP)
            assert len(verifier._cache) <= 5  # type: ignore[attr-defined]
        finally:
            iv_module._MAX_CACHE_ENTRIES = original_cap
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_concurrent_same_token_both_miss_cache_deferred_behavior(
    httpserver: HTTPServer,
) -> None:
    """Test-coverage gap #4: pin the DEFERRED single-flight behavior.

    Memo §2 acknowledges that two concurrent requests with the same
    opaque token both miss the cache and both call introspection
    (single-flight coalescing is a Watch item). This test locks the
    current behavior so a future 'innocent' fix that adds coalescing
    doesn't silently change the contract — the WI must be retired
    explicitly + this assertion flipped from ==2 to ==1."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "user-abc", "iss": _ISSUER}
    )
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        results = await asyncio.gather(
            verifier.verify("same-token", expected_audience=TEST_SURFACE_HTTP),
            verifier.verify("same-token", expected_audience=TEST_SURFACE_HTTP),
        )
        assert all(r.subject == "user-abc" for r in results)
        # CURRENT behavior: both miss → 2 IdP calls. If you're adding
        # single-flight coalescing, retire the WI in the design memo
        # and flip this to `== 1`.
        assert len(httpserver.log) == 2
    finally:
        await verifier.aclose()


# ---------- constructor guards ----------


@pytest.mark.unit
def test_constructor_rejects_zero_cache_ttl() -> None:
    with pytest.raises(ValueError, match=r"cache_ttl_seconds"):
        IntrospectionTokenVerifier(
            issuer=_ISSUER,
            introspection_url="https://example.com/introspect",
            client_id=TEST_CLIENT_ID,
            client_secret=TEST_CLIENT_SECRET,
            audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
            subject_mapper=make_mapper(),
            cache_ttl_seconds=0,
        )


@pytest.mark.unit
def test_constructor_rejects_http_introspection_url_without_opt_in() -> None:
    with pytest.raises(ValueError, match=r"introspection_url must be HTTPS"):
        IntrospectionTokenVerifier(
            issuer=_ISSUER,
            introspection_url="http://example.com/introspect",
            client_id=TEST_CLIENT_ID,
            client_secret=TEST_CLIENT_SECRET,
            audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
            subject_mapper=make_mapper(),
        )


@pytest.mark.unit
def test_client_secret_not_in_repr() -> None:
    """F6: client_secret wrapped in SecretStr; never in __repr__."""
    verifier = IntrospectionTokenVerifier(
        issuer=_ISSUER,
        introspection_url="http://127.0.0.1:1/introspect",
        client_id=TEST_CLIENT_ID,
        client_secret="super-secret-value",
        audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
        subject_mapper=make_mapper(),
        allow_insecure_introspection_url=True,
    )
    text = repr(vars(verifier))
    assert "super-secret-value" not in text
    assert "SecretStr" in text


# ---------- RFC 7662 §2.1 Basic auth + injected client lifecycle ----------


@pytest.mark.unit
async def test_basic_auth_credentials_sent_to_idp(httpserver: HTTPServer) -> None:
    import base64

    expected_basic = (
        "Basic " + base64.b64encode(f"{TEST_CLIENT_ID}:{TEST_CLIENT_SECRET}".encode()).decode()
    )
    httpserver.expect_request(
        "/introspect",
        method="POST",
        headers={"Authorization": expected_basic},
    ).respond_with_json({"active": True, "sub": "user-abc", "iss": _ISSUER})
    verifier = make_introspection_verifier(httpserver.url_for("/introspect"))
    try:
        principal = await verifier.verify("any", expected_audience=TEST_SURFACE_HTTP)
        assert principal.subject == "user-abc"
    finally:
        await verifier.aclose()


@pytest.mark.unit
async def test_injected_http_client_is_not_closed_by_verifier() -> None:
    """Caller-owned httpx.AsyncClient outlives verifier.aclose()."""
    async with httpx.AsyncClient() as injected:
        verifier = IntrospectionTokenVerifier(
            issuer=_ISSUER,
            introspection_url="http://127.0.0.1:1/introspect",
            client_id=TEST_CLIENT_ID,
            client_secret=TEST_CLIENT_SECRET,
            audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
            subject_mapper=make_mapper(),
            http_client=injected,
            allow_insecure_introspection_url=True,
        )
        await verifier.aclose()
        assert not injected.is_closed
