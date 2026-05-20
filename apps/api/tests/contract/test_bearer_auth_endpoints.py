"""Contract tests for Phase C edge-auth on HTTP endpoints.

End-to-end through the full FastAPI app composition (lifespan +
middleware + exception handlers + route layer). Each test boots a
fresh `create_app()` with a configured `IDENTITY_PROVIDERS` env var
so `kernel.token_verifier` is non-None and the bearer-auth code
path is active.

These tests focus on the 401 paths (no bearer, malformed bearer)
and skip-paths (health, metrics, .well-known/oauth-protected-resource)
which exercise the full middleware + exception-handler chain
WITHOUT needing a real JWKS or token signer.

Happy-path bearer verification (valid JWT + real JWKS + signature
verify) lives at the integration tier with `pytest-httpserver`
mocking the IdP -- contract-tier tests focus on shape, not crypto.

## Why an `IDENTITY_PROVIDERS` env var is enough

The verifier is constructed at lifespan start with whatever
JWKS URL is configured. For the no-bearer / malformed-bearer paths
the verifier is never CALLED -- the middleware short-circuits
before that. So the URL being fake is fine.

The fake URL must still be `http://...` so the per-adapter HTTPS
gate doesn't refuse boot; the `allow_insecure_jwks_url=True`
opt-in is set, valid under `app_env=test`.
"""

import json

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_IDPS_JSON = json.dumps(
    [
        {
            "issuer": "https://idp.example.com",
            "jwks_url": "http://idp.example.com/jwks.json",
            "audiences": {
                "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
            },
            "allow_insecure_jwks_url": True,
        }
    ]
)


@pytest.fixture
def bearer_auth_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Boot the app with `IDENTITY_PROVIDERS` set so bearer-auth mode is on.

    No real bearer is required for the 401 paths these tests cover.
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IDENTITY_PROVIDERS", _IDPS_JSON)
    return TestClient(create_app())


# ---------- 401 path: no bearer presented under bearer-auth mode ----------


@pytest.mark.contract
def test_request_without_authorization_returns_401_with_www_authenticate(
    bearer_auth_client: TestClient,
) -> None:
    """When bearer-auth is active and the client sends no Authorization
    header, `get_principal_id` raises HTTP 401. The response MUST
    include the RFC 6750 §3 WWW-Authenticate challenge so OAuth
    clients can render meaningful errors / re-acquire credentials."""
    with bearer_auth_client as client:
        response = client.get("/actors")

    assert response.status_code == 401
    challenge = response.headers.get("WWW-Authenticate", "")
    assert challenge.startswith("Bearer ")
    # The challenge carries the RFC 9728 metadata pointer; clients
    # dereference this to discover the issuer + audiences mapping.
    assert "/.well-known/oauth-protected-resource" in challenge


@pytest.mark.contract
def test_request_with_x_principal_id_only_still_returns_401_under_bearer_auth(
    bearer_auth_client: TestClient,
) -> None:
    """The legacy X-Principal-Id cleartext header is REJECTED under
    bearer-auth mode. Pinning this prevents a misconfigured client
    from accidentally downgrading to the unauthenticated fallback
    by sending only the legacy header."""
    with bearer_auth_client as client:
        response = client.get(
            "/actors",
            headers={"X-Principal-Id": "01900000-0000-7000-8000-000000000a01"},
        )

    assert response.status_code == 401


# ---------- 401 path: malformed Authorization header ----------


@pytest.mark.contract
@pytest.mark.parametrize(
    "header_value",
    [
        "Basic abcdef",  # wrong scheme (RFC 7617)
        "Digest username=foo",  # wrong scheme (RFC 7616)
        "Bearer",  # missing token
        "Bearer ",  # empty token
    ],
)
def test_malformed_authorization_header_returns_401(
    bearer_auth_client: TestClient, header_value: str
) -> None:
    """The middleware's `_extract_bearer_token` raises
    InvalidTokenError(reason="malformed") which the Iter C-4
    handler converts to 401 with `error="malformed"` in the
    challenge."""
    with bearer_auth_client as client:
        response = client.get("/actors", headers={"Authorization": header_value})

    assert response.status_code == 401
    challenge = response.headers.get("WWW-Authenticate", "")
    assert 'error="malformed"' in challenge


# ---------- Skip-path coverage: unauthenticated paths still work ----------


@pytest.mark.contract
def test_health_endpoint_is_unauthenticated_even_under_bearer_auth(
    bearer_auth_client: TestClient,
) -> None:
    """The middleware skip-list MUST keep /health accessible without
    a bearer so k8s liveness probes don't pin DEAD on auth misconfig."""
    with bearer_auth_client as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


@pytest.mark.contract
def test_metrics_endpoint_is_unauthenticated_even_under_bearer_auth(
    bearer_auth_client: TestClient,
) -> None:
    """Prometheus scrape MUST work without credentials."""
    with bearer_auth_client as client:
        response = client.get("/metrics")

    assert response.status_code == 200


@pytest.mark.contract
def test_protected_resource_metadata_is_unauthenticated_even_under_bearer_auth(
    bearer_auth_client: TestClient,
) -> None:
    """RFC 9728 §4.1: the metadata document MUST be served
    unauthenticated so clients can discover issuer info without
    already having a token."""
    with bearer_auth_client as client:
        response = client.get("/.well-known/oauth-protected-resource")

    assert response.status_code == 200
    # The metadata document should be JSON per the RFC.
    body = response.json()
    assert isinstance(body, dict)


# ---------- No regression: legacy mode unchanged with no IdPs ----------


@pytest.mark.contract
def test_no_identity_providers_falls_back_to_x_principal_id_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With IDENTITY_PROVIDERS unset, the legacy
    X-Principal-Id-with-SYSTEM-fallback path stays in effect.
    Pinning this prevents an accidental flip of the default that
    would break every existing deployment."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("IDENTITY_PROVIDERS", raising=False)
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)

    with TestClient(create_app()) as client:
        # No Authorization, no X-Principal-Id -> falls back to
        # SYSTEM_PRINCIPAL_ID under AllowAllAuthorize -> 200.
        response = client.post("/actors", json={"name": "Doga"})

    assert response.status_code == 201


@pytest.mark.contract
def test_bearer_token_present_with_no_identity_providers_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without IDENTITY_PROVIDERS, the middleware no-ops on every
    request -- a bearer header is silently ignored (no verifier to
    call). Pin: a client that mistakenly sends a Bearer header
    against a legacy deployment doesn't 401 or 500, just falls
    through to the legacy path."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("IDENTITY_PROVIDERS", raising=False)

    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"Authorization": "Bearer ignored-token"},
        )

    assert response.status_code == 201
