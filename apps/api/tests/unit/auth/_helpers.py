"""Shared test helpers for `cora.infrastructure.auth.*` unit tests.

Promoted from per-file duplication at the post-ship gate
review (test-coverage reviewer #13). Rule-of-three crossed: the
keypair + signing + mapper + verifier factories were copy-pasted
across `test_jwt_verifier.py`, `test_introspection_verifier.py`,
and `test_idp_registry.py`.

Sibling to `tests/unit/_helpers.py` (the `build_deps` factory used
by every BC's command-handler tests). Same convention: importable
under-`_`-prefix module, NOT auto-loaded; tests opt in via
`from tests.unit.auth._helpers import ...`.

## What this provides

  - **RSA keypair + JWKS server fixture** — `signing_fixture` yields
    `(private_key, kid, jwks_url)` backed by an in-process Werkzeug
    server. Construct JWT-shaped tokens with `sign_jwt(...)`.

  - **Test SubjectMapper** — `make_mapper(kind="human")` returns
    a callable that resolves any `(issuer, subject)` to a fixed
    test UUID. Tests asserting mapper-call shape pass a recording
    mapper directly.

  - **Verifier factories** — `make_jwt_verifier(...)` and
    `make_introspection_verifier(...)` construct adapters with the
    common test config (single HTTP Surface, single algorithm,
    `allow_insecure_*` set to True so tests can use localhost
    Werkzeug endpoints without tripping the production HTTPS gate).

Constants like `TEST_ISSUER`, `TEST_AUD_HTTP`, `TEST_SURFACE_HTTP`,
`FIXED_PRINCIPAL_ID` are exported so tests don't redeclare them.

## Not test_token_issuer.py

The edge-auth design lock §12 lists `cora/infrastructure/auth/test_token_issuer.py`
as a future deliverable for contract tests. That module
ships TestTokenIssuer as a *production-shaped* test fixture that
self-registers as an IdentityProviderConfig. This `_helpers.py` is
the smaller-scope unit-test factory that doesn't require Settings
or registry integration, the two will coexist; this one stays
unit-only.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from pytest_httpserver import HTTPServer

from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.ports.token_verifier import PrincipalKind

TEST_ISSUER = "https://test-idp.example.com"
TEST_AUD_HTTP = "https://cora.test/http"
TEST_AUD_MCP = "https://cora.test/mcp"
TEST_SURFACE_HTTP = UUID("00000000-0000-0000-0000-000000000020")
TEST_SURFACE_MCP = UUID("00000000-0000-0000-0000-000000000022")
FIXED_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000001")

TEST_INTROSPECTION_ISSUER = "https://test-globus.example.com"
TEST_CLIENT_ID = "cora-rs"
TEST_CLIENT_SECRET = "rs-secret"


def make_keypair_with_jwks(
    httpserver: HTTPServer, path: str = "/jwks"
) -> tuple[rsa.RSAPrivateKey, str, str]:
    """Spin up a JWKS endpoint backed by a fresh RSA keypair.

    Returns `(private_key, kid, jwks_url)`. The JWKS contains a single
    RS256 key with the returned `kid`; `sign_jwt(...)` signs tokens
    against this keypair and the verifier fetches from `jwks_url`.

    The previous in-file helpers round-tripped `RSAAlgorithm.to_jwk` →
    `from_jwk` → `to_jwk` — copy-paste artifact; `to_jwk(public_key,
    as_dict=True)` alone is sufficient. Reviewer impl#3.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk: dict[str, Any] = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    kid = f"kid-{path.strip('/')}"
    jwk["kid"] = kid
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    httpserver.expect_request(path).respond_with_json({"keys": [jwk]})
    return private_key, kid, httpserver.url_for(path)


def sign_jwt(
    private_key: rsa.RSAPrivateKey,
    kid: str,
    *,
    sub: str = "user-abc",
    aud: str = TEST_AUD_HTTP,
    iss: str = TEST_ISSUER,
    extra_claims: dict[str, Any] | None = None,
    expires_in: int = 60,
) -> str:
    """Encode an RS256 JWT against the given keypair.

    Defaults match the most common positive-path test shape. Override
    any field for negative-path tests (expired, wrong issuer, etc.).
    """
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
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


def make_mapper(
    *, kind: PrincipalKind = "human"
) -> Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]]:
    """Return a trivial SubjectMapper that resolves any subject to the
    fixed test principal_id + the requested kind.

    For tests asserting the mapper's call shape, write the mapper
    inline instead of using this factory.
    """

    async def mapper(issuer: str, subject: str) -> tuple[UUID, PrincipalKind]:
        _ = (issuer, subject)
        return (FIXED_PRINCIPAL_ID, kind)

    return mapper


def make_jwt_verifier(
    *,
    issuer: str = TEST_ISSUER,
    jwks_url: str,
    audience_for_surface: dict[UUID, str] | None = None,
    subject_mapper: Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]] | None = None,
    algorithms_allowed: list[str] | None = None,
) -> JWTVerifier:
    """Common JWTVerifier construction shape for unit tests.

    Defaults: single HTTP Surface, RS256-only, fixed test mapper,
    allow_insecure_jwks_url=True (tests use localhost Werkzeug
    endpoints; production posture is HTTPS-only).
    """
    return JWTVerifier(
        issuer=issuer,
        jwks_url=jwks_url,
        audience_for_surface=audience_for_surface or {TEST_SURFACE_HTTP: TEST_AUD_HTTP},
        subject_mapper=subject_mapper or make_mapper(),
        algorithms_allowed=algorithms_allowed or ["RS256"],
        allow_insecure_jwks_url=True,
    )


def make_introspection_verifier(
    introspection_url: str,
    *,
    issuer: str = TEST_INTROSPECTION_ISSUER,
    audience_for_surface: dict[UUID, str] | None = None,
    subject_mapper: Callable[[str, str], Awaitable[tuple[UUID, PrincipalKind]]] | None = None,
    cache_ttl_seconds: int = 30,
) -> IntrospectionVerifier:
    """Common IntrospectionVerifier construction shape for unit tests."""
    return IntrospectionVerifier(
        issuer=issuer,
        introspection_url=introspection_url,
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        audience_for_surface=audience_for_surface or {TEST_SURFACE_HTTP: TEST_AUD_HTTP},
        subject_mapper=subject_mapper or make_mapper(),
        cache_ttl_seconds=cache_ttl_seconds,
        allow_insecure_introspection_url=True,
    )
