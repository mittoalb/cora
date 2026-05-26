"""Unit tests for `cora.infrastructure.auth.idp_registry.IdentityProviderRegistry`.

The registry routes inbound tokens to the right verifier. Pins:

  - empty registry construction rejected
  - duplicate JWT issuer rejected
  - JWT-shape detection → routes to matching JwtTokenVerifier
  - opaque-shape → routes to IntrospectionTokenVerifier
  - JWT with unregistered iss → InvalidTokenError(wrong_issuer)
  - opaque without IntrospectionTokenVerifier → InvalidTokenError(malformed)
  - empty / garbage / missing-iss → InvalidTokenError(malformed)
  - JWT-only deployment + introspection-only deployment shape symmetry
  - token-length cap (gate-review F11) — DoS guard at registry boundary
"""

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_httpserver import HTTPServer

from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
from cora.infrastructure.ports.token_verifier import InvalidTokenError
from tests.unit.auth._helpers import (
    TEST_AUD_HTTP,
    TEST_SURFACE_HTTP,
    make_introspection_verifier,
    make_jwt_verifier,
    make_keypair_with_jwks,
)

_ISSUER_A = "https://idp-a.example.com"
_ISSUER_B = "https://idp-b.example.com"


def _sign_for_issuer(
    private_key: rsa.RSAPrivateKey,
    kid: str,
    *,
    iss: str,
    sub: str = "user-abc",
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": iss,
        "sub": sub,
        "aud": TEST_AUD_HTTP,
        "iat": now,
        "exp": now + 60,
    }
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


# ---------- construction guards ----------


@pytest.mark.unit
def test_empty_registry_rejected() -> None:
    with pytest.raises(ValueError, match="at least one verifier"):
        IdentityProviderRegistry(jwt_verifiers=[], introspection_token_verifier=None)


@pytest.mark.unit
def test_duplicate_jwt_issuer_rejected(httpserver: HTTPServer) -> None:
    _, _, jwks_url = make_keypair_with_jwks(httpserver, "/jwks")
    v1 = make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_url)
    v2 = make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_url)
    with pytest.raises(ValueError, match="Duplicate"):
        IdentityProviderRegistry(jwt_verifiers=[v1, v2])


# ---------- routing ----------


@pytest.mark.unit
async def test_jwt_token_routed_to_matching_verifier(
    httpserver: HTTPServer,
) -> None:
    private_a, kid_a, jwks_a = make_keypair_with_jwks(httpserver, "/idp-a/jwks")
    private_b, kid_b, jwks_b = make_keypair_with_jwks(httpserver, "/idp-b/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[
            make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_a),
            make_jwt_verifier(issuer=_ISSUER_B, jwks_url=jwks_b),
        ],
    )

    token_a = _sign_for_issuer(private_a, kid_a, iss=_ISSUER_A, sub="user-a")
    principal_a = await registry.verify(token_a, expected_audience=TEST_SURFACE_HTTP)
    assert principal_a.issuer == _ISSUER_A
    assert principal_a.subject == "user-a"

    token_b = _sign_for_issuer(private_b, kid_b, iss=_ISSUER_B, sub="user-b")
    principal_b = await registry.verify(token_b, expected_audience=TEST_SURFACE_HTTP)
    assert principal_b.issuer == _ISSUER_B
    assert principal_b.subject == "user-b"


@pytest.mark.unit
async def test_jwt_with_unknown_issuer_rejected(httpserver: HTTPServer) -> None:
    private_a, kid_a, jwks_a = make_keypair_with_jwks(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_a)],
    )
    rogue = _sign_for_issuer(private_a, kid_a, iss="https://rogue.example.com")
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify(rogue, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "wrong_issuer"


@pytest.mark.unit
async def test_opaque_token_routed_to_introspection(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "globus-user", "iss": "https://test-globus.example.com"}
    )
    registry = IdentityProviderRegistry(
        jwt_verifiers=[],
        introspection_token_verifier=make_introspection_verifier(httpserver.url_for("/introspect")),
    )
    principal = await registry.verify("opaque-abc-no-dots", expected_audience=TEST_SURFACE_HTTP)
    assert principal.subject == "globus-user"


@pytest.mark.unit
async def test_opaque_token_without_introspection_rejected(
    httpserver: HTTPServer,
) -> None:
    _, _, jwks_url = make_keypair_with_jwks(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_url)],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify("opaque-no-dots", expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "malformed"
    assert "no IntrospectionTokenVerifier" in exc.value.detail


# ---------- shape symmetry (test-coverage gap #11) ----------


@pytest.mark.unit
async def test_jwt_only_deployment_works(httpserver: HTTPServer) -> None:
    """JWT-only deployment (no introspection) accepts JWT tokens."""
    private_a, kid_a, jwks_a = make_keypair_with_jwks(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_a)],
        introspection_token_verifier=None,
    )
    token = _sign_for_issuer(private_a, kid_a, iss=_ISSUER_A)
    principal = await registry.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert principal.issuer == _ISSUER_A


@pytest.mark.unit
async def test_introspection_only_deployment_works(httpserver: HTTPServer) -> None:
    """Introspection-only deployment (Globus-only) accepts opaque tokens."""
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {"active": True, "sub": "globus-user", "iss": "https://test-globus.example.com"}
    )
    registry = IdentityProviderRegistry(
        jwt_verifiers=[],
        introspection_token_verifier=make_introspection_verifier(httpserver.url_for("/introspect")),
    )
    principal = await registry.verify("opaque-x", expected_audience=TEST_SURFACE_HTTP)
    assert principal.subject == "globus-user"


# ---------- malformed input ----------


@pytest.mark.unit
async def test_empty_token_rejected(httpserver: HTTPServer) -> None:
    _, _, jwks_url = make_keypair_with_jwks(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_url)],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify("", expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "malformed"


@pytest.mark.unit
async def test_jwt_shaped_garbage_rejected_at_unverified_peek(
    httpserver: HTTPServer,
) -> None:
    """3-dot string that isn't valid base64-encoded JWT → malformed."""
    _, _, jwks_url = make_keypair_with_jwks(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_url)],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify("garbage.garbage.garbage", expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "malformed"


@pytest.mark.unit
async def test_jwt_missing_iss_claim_rejected(httpserver: HTTPServer) -> None:
    private_key, kid, _ = make_keypair_with_jwks(httpserver, "/jwks")
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = int(time.time())
    no_iss = jwt.encode(
        {"sub": "x", "aud": TEST_AUD_HTTP, "iat": now, "exp": now + 60},
        private_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url="https://example.com/jwks")],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify(no_iss, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "malformed"


# ---------- F11: DoS guard via token-length cap ----------


@pytest.mark.unit
async def test_excessive_length_token_rejected_at_boundary(
    httpserver: HTTPServer,
) -> None:
    """Gate-review F11: attacker submitting a multi-megabyte string
    with two dots would otherwise force the registry to base64-decode
    huge segments via `jwt.decode(..., verify_signature=False)`. The
    cap rejects before parse so no CPU is burned on attacker input."""
    _, _, jwks_url = make_keypair_with_jwks(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[make_jwt_verifier(issuer=_ISSUER_A, jwks_url=jwks_url)],
    )
    # 16 KB token (well past the 8192-byte cap).
    huge = "a" * 16_384 + ".b.c"
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify(huge, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "malformed"
    assert "exceeds maximum" in exc.value.detail
