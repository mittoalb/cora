"""Unit tests for `cora.infrastructure.auth.jwt_verifier.JWTVerifier`.

Uses `_helpers.signing_fixture` to mint real RS256-signed JWTs per
test backed by an in-process JWKS endpoint, so the verifier exercises
its full PyJWT + PyJWKClient path without a network call.

Pins:
  - happy path → VerifiedPrincipal with right claims
  - 8 of 9 InvalidTokenError reason codes (introspection_inactive is
    introspection-only); `unknown_subject` raised via SubjectMapper
    wrapping
  - audience-per-Surface anti-replay (RFC 8707 §3)
  - alg=none: case-insensitive + whitespace whitelist guard
  - HTTPS enforcement on jwks_url + opt-in escape hatch
  - algorithm-confusion attack: HS256 signed with RSA public key as
    HMAC secret (CVE-2015-9235 class) MUST fail
"""

import time
from uuid import UUID

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
from tests.unit.auth._helpers import (
    FIXED_PRINCIPAL_ID,
    TEST_AUD_HTTP,
    TEST_AUD_MCP,
    TEST_ISSUER,
    TEST_SURFACE_HTTP,
    TEST_SURFACE_MCP,
    make_jwt_verifier,
    make_keypair_with_jwks,
    make_mapper,
    sign_jwt,
)


@pytest.fixture
def signing_fixture(httpserver: HTTPServer) -> tuple[rsa.RSAPrivateKey, str, str]:
    return make_keypair_with_jwks(httpserver, "/jwks")


# ---------- happy path + claim extraction ----------


@pytest.mark.unit
async def test_verify_valid_token_returns_verified_principal(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    token = sign_jwt(private_key, kid, sub="user-abc")
    principal = await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert isinstance(principal, VerifiedPrincipal)
    assert principal.principal_id == FIXED_PRINCIPAL_ID
    assert principal.subject == "user-abc"
    assert principal.issuer == TEST_ISSUER
    assert principal.kind == "human"
    assert principal.scopes == frozenset()


@pytest.mark.unit
async def test_verify_extracts_scopes_from_space_delimited_string(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    token = sign_jwt(private_key, kid, extra_claims={"scope": "runs:read plans:write"})
    principal = await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert principal.scopes == frozenset({"runs:read", "plans:write"})


@pytest.mark.unit
async def test_verify_extracts_scopes_from_microsoft_scp_list(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    token = sign_jwt(private_key, kid, extra_claims={"scp": ["runs:read", "plans:write"]})
    principal = await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert principal.scopes == frozenset({"runs:read", "plans:write"})


# ---------- reason-code coverage ----------


@pytest.mark.unit
async def test_verify_rejects_audience_mismatch(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """RFC 8707 §3 anti-replay across resource servers."""
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(
        jwks_url=jwks_url,
        audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP, TEST_SURFACE_MCP: TEST_AUD_MCP},
    )
    http_token = sign_jwt(private_key, kid, aud=TEST_AUD_HTTP)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(http_token, expected_audience=TEST_SURFACE_MCP)
    assert exc.value.reason == "wrong_audience"


@pytest.mark.unit
async def test_verify_rejects_unconfigured_surface(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    _, _, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify("any-token", expected_audience=TEST_SURFACE_MCP)
    assert exc.value.reason == "wrong_audience"


@pytest.mark.unit
async def test_verify_rejects_expired_token(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    token = sign_jwt(private_key, kid, expires_in=-1)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "expired"


@pytest.mark.unit
async def test_verify_rejects_token_with_future_nbf(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """`not_yet_valid` reason-code coverage."""
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    future_nbf = int(time.time()) + 3600
    token = sign_jwt(private_key, kid, extra_claims={"nbf": future_nbf})
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "not_yet_valid"


@pytest.mark.unit
async def test_verify_rejects_wrong_issuer(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    token = sign_jwt(private_key, kid, iss="https://hostile-idp.example.com")
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "wrong_issuer"


@pytest.mark.unit
async def test_verify_rejects_bad_signature(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """Token signed by a different keypair under the same kid."""
    _, kid, jwks_url = signing_fixture
    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    other_pem = other_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = int(time.time())
    bad_token = jwt.encode(
        {"iss": TEST_ISSUER, "sub": "user-abc", "aud": TEST_AUD_HTTP, "iat": now, "exp": now + 60},
        other_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(bad_token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "bad_signature"


@pytest.mark.unit
async def test_verify_rejects_malformed_token(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    _, _, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify("not.a.jwt", expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason in {"malformed", "bad_signature"}


# ---------- algorithm-confusion attack (CVE-2015-9235 class) ----------


@pytest.mark.unit
async def test_verify_rejects_hand_crafted_hs256_signed_with_rsa_public_key(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """Classic JOSE algorithm-confusion attack (Tim McLean, 2015 /
    CVE-2015-9235): the attacker reads the RSA public key (it IS
    public) and constructs a token with `alg=HS256` using the public
    key bytes as the HMAC shared secret. A naive verifier that picks
    the verification algorithm from the token's `alg` header would
    accept it.

    PyJWT 2.x blocks this at `jwt.encode()` — refuses to use an
    asymmetric key as an HMAC secret — so we hand-craft the token
    via base64 + raw HMAC to simulate an attacker who isn't using
    PyJWT. The verifier's defense is `algorithms=["RS256"]` pinned
    at decode time; the hand-crafted HS256 token MUST fail."""
    import base64
    import hashlib
    import hmac
    import json

    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)  # RS256-only

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header_json = json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}).encode()
    now = int(time.time())
    payload_json = json.dumps(
        {"iss": TEST_ISSUER, "sub": "attacker", "aud": TEST_AUD_HTTP, "iat": now, "exp": now + 60}
    ).encode()
    signing_input = f"{_b64url(header_json)}.{_b64url(payload_json)}".encode()
    signature = hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    confusion_token = f"{signing_input.decode()}.{_b64url(signature)}"

    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(confusion_token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason in {"unsupported_algorithm", "bad_signature"}


@pytest.mark.unit
async def test_verify_rejects_unsupported_algorithm_in_whitelist(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """HS256-signed token with a guessed secret → unsupported_algorithm."""
    _, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url)
    now = int(time.time())
    hs256_token = jwt.encode(
        {"iss": TEST_ISSUER, "sub": "user-abc", "aud": TEST_AUD_HTTP, "iat": now, "exp": now + 60},
        "shared-secret-that-is-at-least-32-bytes-long",
        algorithm="HS256",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(hs256_token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason in {"unsupported_algorithm", "bad_signature"}


# ---------- audience-binding + F2 constructor guards ----------


@pytest.mark.unit
def test_constructor_rejects_empty_algorithms() -> None:
    with pytest.raises(ValueError, match="algorithms_allowed"):
        JWTVerifier(
            issuer=TEST_ISSUER,
            jwks_url="https://example.com/jwks",
            audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
            subject_mapper=make_mapper(),
            algorithms_allowed=[],
        )


@pytest.mark.unit
def test_constructor_rejects_alg_none_case_insensitive() -> None:
    for variant in ["none", "NONE", "NoNe", " none ", "None "]:
        with pytest.raises(ValueError, match=r"alg=none"):
            JWTVerifier(
                issuer=TEST_ISSUER,
                jwks_url="https://example.com/jwks",
                audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
                subject_mapper=make_mapper(),
                algorithms_allowed=[variant, "RS256"],
            )


@pytest.mark.unit
def test_constructor_rejects_http_jwks_url_without_opt_in() -> None:
    with pytest.raises(ValueError, match=r"jwks_url must be HTTPS"):
        JWTVerifier(
            issuer=TEST_ISSUER,
            jwks_url="http://example.com/jwks",
            audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
            subject_mapper=make_mapper(),
            algorithms_allowed=["RS256"],
        )


@pytest.mark.unit
def test_constructor_accepts_http_jwks_url_with_opt_in() -> None:
    JWTVerifier(
        issuer=TEST_ISSUER,
        jwks_url="http://127.0.0.1:8000/jwks",
        audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
        subject_mapper=make_mapper(),
        algorithms_allowed=["RS256"],
        allow_insecure_jwks_url=True,
    )


# ---------- subject_mapper plumbing ----------


@pytest.mark.unit
async def test_subject_mapper_receives_issuer_and_subject(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    captured: list[tuple[str, str]] = []

    async def capturing_mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        captured.append((issuer, subject))
        return (FIXED_PRINCIPAL_ID, "human")

    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url, subject_mapper=capturing_mapper)
    token = sign_jwt(private_key, kid, sub="user-xyz")
    await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert captured == [(TEST_ISSUER, "user-xyz")]


@pytest.mark.unit
async def test_service_account_kind_propagates_to_verified_principal(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(
        jwks_url=jwks_url, subject_mapper=make_mapper(kind="service_account")
    )
    token = sign_jwt(private_key, kid)
    principal = await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert principal.kind == "service_account"


@pytest.mark.unit
async def test_subject_mapper_returning_nil_uuid_rejected(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    async def nil_mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        return (UUID(int=0), "human")

    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url, subject_mapper=nil_mapper)
    token = sign_jwt(private_key, kid)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "unknown_subject"


@pytest.mark.unit
async def test_subject_mapper_returning_invalid_kind_rejected(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    async def bad_kind_mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        return (FIXED_PRINCIPAL_ID, "admin")  # type: ignore[return-value]

    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url, subject_mapper=bad_kind_mapper)
    token = sign_jwt(private_key, kid)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "malformed"


@pytest.mark.unit
async def test_subject_mapper_raising_wraps_as_unknown_subject(
    signing_fixture: tuple[rsa.RSAPrivateKey, str, str],
) -> None:
    """Mapper exceptions → InvalidTokenError(unknown_subject) so 401 not 500."""

    async def raising_mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        raise KeyError("no actor for this subject")

    private_key, kid, jwks_url = signing_fixture
    verifier = make_jwt_verifier(jwks_url=jwks_url, subject_mapper=raising_mapper)
    token = sign_jwt(private_key, kid)
    with pytest.raises(InvalidTokenError) as exc:
        await verifier.verify(token, expected_audience=TEST_SURFACE_HTTP)
    assert exc.value.reason == "unknown_subject"


# ---------- verifier shape ----------


@pytest.mark.unit
def test_verifier_exposes_its_issuer() -> None:
    verifier = JWTVerifier(
        issuer=TEST_ISSUER,
        jwks_url="https://example.com/jwks",
        audience_for_surface={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
        subject_mapper=make_mapper(),
        algorithms_allowed=["RS256"],
    )
    assert verifier.issuer == TEST_ISSUER
