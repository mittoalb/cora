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
        )
        await verifier.aclose()
        # Injected client must still be usable.
        assert not injected.is_closed
