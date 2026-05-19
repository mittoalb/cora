"""Unit tests for `cora.infrastructure.auth.idp_registry.IdentityProviderRegistry`.

The registry routes inbound tokens to the right verifier. Pins:

  - empty registry construction rejected
  - duplicate JWT issuer rejected
  - JWT-shape detection (3-dot base64) → routes to matching JWTVerifier
  - opaque-shape (no 3-dot) → routes to IntrospectionVerifier
  - JWT with unregistered iss → InvalidTokenError(reason="wrong_issuer")
  - opaque without IntrospectionVerifier → InvalidTokenError(reason="malformed")
  - empty string → InvalidTokenError(reason="malformed")
  - JWT-shaped garbage (3-dot base64 but invalid payload) → InvalidTokenError(reason="malformed")
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_httpserver import HTTPServer

from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.ports.token_verifier import (
    InvalidTokenError,
    PrincipalKind,
)

_ISSUER_A = "https://idp-a.example.com"
_ISSUER_B = "https://idp-b.example.com"
_AUD = "https://cora.test/http"
_SURFACE = UUID("00000000-0000-0000-0000-000000000020")
_FIXED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000001")


def _make_mapper() -> Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]:
    async def mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        return (_FIXED_PRINCIPAL, "human")

    return mapper


def _make_keypair_and_jwks_url(
    httpserver: HTTPServer, path: str
) -> tuple[rsa.RSAPrivateKey, str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    from jwt.algorithms import RSAAlgorithm

    jwk = RSAAlgorithm.to_jwk(
        RSAAlgorithm.from_jwk(RSAAlgorithm.to_jwk(private_key.public_key())),
        as_dict=True,
    )
    kid = f"kid-{path.strip('/')}"
    jwk["kid"] = kid
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    httpserver.expect_request(path).respond_with_json({"keys": [jwk]})
    return private_key, kid, httpserver.url_for(path)


def _sign(
    private_key: rsa.RSAPrivateKey,
    kid: str,
    *,
    iss: str,
    sub: str = "user-abc",
    aud: str = _AUD,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "iat": now,
        "exp": now + 60,
    }
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


def _make_jwt_verifier(issuer: str, jwks_url: str) -> JWTVerifier:
    return JWTVerifier(
        issuer=issuer,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE: _AUD},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )


def _make_introspection_verifier(introspection_url: str) -> IntrospectionVerifier:
    return IntrospectionVerifier(
        issuer="https://opaque-idp.example.com",
        introspection_url=introspection_url,
        client_id="cora-rs",
        client_secret="rs-secret",
        audience_for_surface={_SURFACE: _AUD},
        subject_mapper=_make_mapper(),
    )


@pytest.mark.unit
def test_empty_registry_rejected() -> None:
    with pytest.raises(ValueError, match="at least one verifier"):
        IdentityProviderRegistry(jwt_verifiers=[], introspection_verifier=None)


@pytest.mark.unit
def test_duplicate_jwt_issuer_rejected(httpserver: HTTPServer) -> None:
    _, _, jwks_url = _make_keypair_and_jwks_url(httpserver, "/jwks")
    v1 = _make_jwt_verifier(_ISSUER_A, jwks_url)
    v2 = _make_jwt_verifier(_ISSUER_A, jwks_url)
    with pytest.raises(ValueError, match="Duplicate"):
        IdentityProviderRegistry(jwt_verifiers=[v1, v2])


@pytest.mark.unit
async def test_jwt_token_routed_to_matching_verifier(
    httpserver: HTTPServer,
) -> None:
    private_a, kid_a, jwks_a = _make_keypair_and_jwks_url(httpserver, "/idp-a/jwks")
    private_b, kid_b, jwks_b = _make_keypair_and_jwks_url(httpserver, "/idp-b/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[
            _make_jwt_verifier(_ISSUER_A, jwks_a),
            _make_jwt_verifier(_ISSUER_B, jwks_b),
        ],
    )

    # Token from IDP-A should verify even with IDP-B registered.
    token_a = _sign(private_a, kid_a, iss=_ISSUER_A, sub="user-a")
    principal_a = await registry.verify(token_a, expected_audience=_SURFACE)
    assert principal_a.issuer == _ISSUER_A
    assert principal_a.subject == "user-a"

    # Token from IDP-B routes independently.
    token_b = _sign(private_b, kid_b, iss=_ISSUER_B, sub="user-b")
    principal_b = await registry.verify(token_b, expected_audience=_SURFACE)
    assert principal_b.issuer == _ISSUER_B
    assert principal_b.subject == "user-b"


@pytest.mark.unit
async def test_jwt_with_unknown_issuer_rejected(httpserver: HTTPServer) -> None:
    private_a, kid_a, jwks_a = _make_keypair_and_jwks_url(httpserver, "/jwks")
    registry = IdentityProviderRegistry(
        jwt_verifiers=[_make_jwt_verifier(_ISSUER_A, jwks_a)],
    )
    # Sign as ISSUER_B which isn't registered.
    rogue = _sign(private_a, kid_a, iss="https://rogue.example.com")
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify(rogue, expected_audience=_SURFACE)
    assert exc.value.reason == "wrong_issuer"


@pytest.mark.unit
async def test_opaque_token_routed_to_introspection(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request("/introspect", method="POST").respond_with_json(
        {
            "active": True,
            "sub": "globus-user",
            "iss": "https://opaque-idp.example.com",
        }
    )
    registry = IdentityProviderRegistry(
        jwt_verifiers=[],
        introspection_verifier=_make_introspection_verifier(httpserver.url_for("/introspect")),
    )
    principal = await registry.verify("opaque-abc-no-dots", expected_audience=_SURFACE)
    assert principal.subject == "globus-user"


@pytest.mark.unit
async def test_opaque_token_without_introspection_rejected() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    from jwt.algorithms import RSAAlgorithm

    jwk_dict = RSAAlgorithm.to_jwk(
        RSAAlgorithm.from_jwk(RSAAlgorithm.to_jwk(private_key.public_key())),
        as_dict=True,
    )
    _ = jwk_dict
    # Construct a JWT-only registry, then send an opaque token.
    registry = IdentityProviderRegistry(
        jwt_verifiers=[_make_jwt_verifier(_ISSUER_A, "https://example.com/jwks")],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify("opaque-no-dots", expected_audience=_SURFACE)
    assert exc.value.reason == "malformed"
    assert "no IntrospectionVerifier" in exc.value.detail


@pytest.mark.unit
async def test_empty_token_rejected() -> None:
    registry = IdentityProviderRegistry(
        jwt_verifiers=[_make_jwt_verifier(_ISSUER_A, "https://example.com/jwks")],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify("", expected_audience=_SURFACE)
    assert exc.value.reason == "malformed"


@pytest.mark.unit
async def test_jwt_shaped_garbage_rejected_at_unverified_peek() -> None:
    """3-dot string that isn't valid base64-encoded JWT → malformed
    at the unverified-header peek (not bad_signature)."""
    registry = IdentityProviderRegistry(
        jwt_verifiers=[_make_jwt_verifier(_ISSUER_A, "https://example.com/jwks")],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify("garbage.garbage.garbage", expected_audience=_SURFACE)
    assert exc.value.reason == "malformed"


@pytest.mark.unit
async def test_jwt_missing_iss_claim_rejected(httpserver: HTTPServer) -> None:
    """Valid JWT-shaped + parseable but no `iss` claim → malformed."""
    private_key, kid, _ = _make_keypair_and_jwks_url(httpserver, "/jwks")
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = int(time.time())
    no_iss = jwt.encode(
        {"sub": "x", "aud": _AUD, "iat": now, "exp": now + 60},
        private_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )
    registry = IdentityProviderRegistry(
        jwt_verifiers=[_make_jwt_verifier(_ISSUER_A, "https://example.com/jwks")],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await registry.verify(no_iss, expected_audience=_SURFACE)
    assert exc.value.reason == "malformed"
