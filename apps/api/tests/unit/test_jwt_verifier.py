"""Unit tests for `cora.infrastructure.auth.jwt_verifier.JWTVerifier`.

Mints real RS256-signed JWTs per test using an ephemeral keypair +
an in-process JWKS, so the verifier exercises its full PyJWT +
PyJWKClient path without a network call. The `_signing_fixture`
exposes an HTTP server (pytest-httpserver) that serves the JWKS at
a real URL; PyJWKClient fetches it once and caches.

Pins:
  - happy path: valid token → VerifiedPrincipal with right claims
  - audience-per-Surface: token for Surface A must fail against
    Surface B's expected_audience (RFC 8707 §3 anti-replay)
  - all the InvalidTokenError reason codes (bad_signature, expired,
    wrong_audience, wrong_issuer, malformed, unsupported_algorithm)
  - subject_mapper invocation (signature + return shape)
  - AH4: alg=none rejected at construction
  - AH4: empty algorithms_allowed rejected at construction
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_httpserver import HTTPServer

from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.ports.token_verifier import (
    InvalidTokenError,
    PrincipalKind,
    VerifiedPrincipal,
)

_ISSUER = "https://test-idp.example.com"
_AUD_HTTP = "https://cora.test/http"
_AUD_MCP = "https://cora.test/mcp"
_SURFACE_HTTP = UUID("00000000-0000-0000-0000-000000000020")
_SURFACE_MCP = UUID("00000000-0000-0000-0000-000000000022")


def _make_keypair() -> tuple[rsa.RSAPrivateKey, str, dict[str, Any]]:
    """Return (private_key, kid, jwks_dict) with a fresh RS256 keypair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    # PyJWT's PyJWKClient parses JWKS dicts; build one minimal entry.
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    from jwt.algorithms import RSAAlgorithm

    public_jwk = RSAAlgorithm.to_jwk(
        RSAAlgorithm.from_jwk(  # round-trip to dict form
            RSAAlgorithm.to_jwk(public_key)
        ),
        as_dict=True,
    )
    kid = "test-kid-1"
    public_jwk["kid"] = kid
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    _ = public_pem
    return private_key, kid, {"keys": [public_jwk]}


def _sign(
    private_key: rsa.RSAPrivateKey,
    kid: str,
    *,
    sub: str = "user-abc",
    aud: str = _AUD_HTTP,
    iss: str = _ISSUER,
    extra_claims: dict[str, Any] | None = None,
    expires_in: int = 60,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "iat": now,
        "exp": now + expires_in,
    }
    if extra_claims:
        claims.update(extra_claims)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(
        claims,
        private_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


_FIXED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000001")


def _make_mapper(
    *, kind: PrincipalKind = "human"
) -> Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]:
    async def mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        return (_FIXED_PRINCIPAL, kind)

    return mapper


@pytest.fixture
def signing_fixture(httpserver: HTTPServer) -> tuple[rsa.RSAPrivateKey, str, str]:
    """Spin up an in-process JWKS endpoint + return (private_key, kid, jwks_url)."""
    private_key, kid, jwks = _make_keypair()
    httpserver.expect_request("/jwks").respond_with_json(jwks)
    jwks_url = httpserver.url_for("/jwks")
    return private_key, kid, jwks_url


@pytest.mark.unit
async def test_verify_valid_token_returns_verified_principal(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid, sub="user-abc")
    principal = await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert isinstance(principal, VerifiedPrincipal)
    assert principal.principal_id == _FIXED_PRINCIPAL
    assert principal.subject == "user-abc"
    assert principal.issuer == _ISSUER
    assert principal.kind == "human"
    assert principal.scopes == frozenset()


@pytest.mark.unit
async def test_verify_extracts_scopes_from_space_delimited_string(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid, extra_claims={"scope": "runs:read plans:write"})
    principal = await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert principal.scopes == frozenset({"runs:read", "plans:write"})


@pytest.mark.unit
async def test_verify_extracts_scopes_from_microsoft_scp_list(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid, extra_claims={"scp": ["runs:read", "plans:write"]})
    principal = await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert principal.scopes == frozenset({"runs:read", "plans:write"})


@pytest.mark.unit
async def test_verify_rejects_audience_mismatch(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """A token issued for the HTTP Surface must fail against the
    MCP Surface — RFC 8707 §3 anti-replay across resource servers."""
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP, _SURFACE_MCP: _AUD_MCP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    http_token = _sign(private_key, kid, aud=_AUD_HTTP)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(http_token, expected_audience=_SURFACE_MCP)
    assert exc.value.reason == "wrong_audience"


@pytest.mark.unit
async def test_verify_rejects_unknown_surface(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """expected_audience pointing at a Surface the verifier wasn't
    configured for → wrong_audience (defensive; the registry
    normally feeds only configured surfaces, but the verifier
    enforces its own contract)."""
    _, _, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},  # MCP NOT configured
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify("any-token", expected_audience=_SURFACE_MCP)
    assert exc.value.reason == "wrong_audience"


@pytest.mark.unit
async def test_verify_rejects_expired_token(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid, expires_in=-1)  # already expired
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert exc.value.reason == "expired"


@pytest.mark.unit
async def test_verify_rejects_wrong_issuer(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid, iss="https://hostile-idp.example.com")
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert exc.value.reason == "wrong_issuer"


@pytest.mark.unit
async def test_verify_rejects_bad_signature(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """A token signed by a different keypair (different kid not in
    JWKS) → bad_signature (PyJWKClient raises lookup failure)."""
    _, kid, jwks_url = signing_fixture
    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    # Sign with different key but same kid the JWKS knows about —
    # the signing key matches kid but the cryptographic signature won't
    # verify against the JWKS public key.
    other_pem = other_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = int(time.time())
    bad_token = jwt.encode(
        {
            "iss": _ISSUER,
            "sub": "user-abc",
            "aud": _AUD_HTTP,
            "iat": now,
            "exp": now + 60,
        },
        other_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(bad_token, expected_audience=_SURFACE_HTTP)
    assert exc.value.reason == "bad_signature"


@pytest.mark.unit
async def test_verify_rejects_malformed_token(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    _, _, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify("not.a.jwt", expected_audience=_SURFACE_HTTP)
    # PyJWT's decode path raises DecodeError for unparseable structure;
    # we map to "malformed" or "bad_signature" depending on which step
    # failed first. Both are acceptable for unparseable strings.
    assert exc.value.reason in {"malformed", "bad_signature"}


@pytest.mark.unit
async def test_verify_rejects_unsupported_algorithm(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """A token signed with HS256 but verifier configured for RS256 only
    → unsupported_algorithm (the algorithm-confusion attack class)."""
    _, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],  # only RS256
    )
    # Sign with HS256 using a guessed shared secret.
    now = int(time.time())
    hs256_token = jwt.encode(
        {
            "iss": _ISSUER,
            "sub": "user-abc",
            "aud": _AUD_HTTP,
            "iat": now,
            "exp": now + 60,
        },
        "shared-secret",
        algorithm="HS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(hs256_token, expected_audience=_SURFACE_HTTP)
    # PyJWKClient will try to find an RS256 key for kid; the key it
    # finds is RS256. PyJWT's decode then sees the token's `alg` is
    # HS256 (not in our whitelist) and raises InvalidAlgorithmError,
    # OR signature verification fails first as bad_signature. Both
    # are valid rejection modes; the security property holds.
    assert exc.value.reason in {"unsupported_algorithm", "bad_signature"}


@pytest.mark.unit
def test_constructor_rejects_alg_none() -> None:
    """AH4: alg=none must not be in algorithms_allowed."""
    with pytest.raises(ValueError, match=r"alg=none|AH4"):
        JWTVerifier(
            issuer=_ISSUER,
            jwks_url="https://example.com/jwks",
            audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
            subject_mapper=_make_mapper(),
            algorithms_allowed=["none", "RS256"],
        )


@pytest.mark.unit
def test_constructor_rejects_empty_algorithms() -> None:
    """AH4: algorithms_allowed must be non-empty (explicit > implicit)."""
    with pytest.raises(ValueError, match="algorithms_allowed"):
        JWTVerifier(
            issuer=_ISSUER,
            jwks_url="https://example.com/jwks",
            audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
            subject_mapper=_make_mapper(),
            algorithms_allowed=[],
        )


@pytest.mark.unit
async def test_subject_mapper_receives_issuer_and_subject(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    captured: list[tuple[str, str]] = []

    async def capturing_mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        captured.append((issuer, subject))
        return (_FIXED_PRINCIPAL, "human")

    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=capturing_mapper,
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid, sub="user-xyz")
    await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert captured == [(_ISSUER, "user-xyz")]


@pytest.mark.unit
async def test_service_account_kind_overrides_default(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """The subject_mapper can return kind=service_account; the verifier
    surfaces it on VerifiedPrincipal."""
    private_key, kid, jwks_url = signing_fixture
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url=jwks_url,
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(kind="service_account"),
        algorithms_allowed=["RS256"],
    )
    token = _sign(private_key, kid)
    principal = await verifier.verify(token, expected_audience=_SURFACE_HTTP)
    assert principal.kind == "service_account"


@pytest.mark.unit
def test_verifier_exposes_its_issuer() -> None:
    verifier = JWTVerifier(
        issuer=_ISSUER,
        jwks_url="https://example.com/jwks",
        audience_for_surface={_SURFACE_HTTP: _AUD_HTTP},
        subject_mapper=_make_mapper(),
        algorithms_allowed=["RS256"],
    )
    assert verifier.issuer == _ISSUER


# Suppress unused-import flags (uuid4 used by future tests).
_ = uuid4
