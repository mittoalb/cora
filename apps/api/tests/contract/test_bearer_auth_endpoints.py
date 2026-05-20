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

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false

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


# ---------- Happy-path bearer end-to-end (gate-review BLOCKING fill-in) ----------


@pytest.mark.contract
def test_bearer_verified_principal_reaches_event_store_via_full_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate-review BLOCKING test gap: end-to-end pin that the bearer-
    verified principal_id (NOT SYSTEM, NOT any X-Principal-Id value)
    flows all the way through middleware -> get_principal_id -> route
    handler -> append_to_event_store. Without this, a future drift
    that silently routed legacy SYSTEM principal_id past a verified
    bearer would not be caught at PR time.

    Uses a monkeypatch seam that swaps `cora.infrastructure.deps.
    build_kernel` so the constructed kernel has a STUB TokenVerifier
    instead of the real `IdentityProviderRegistry` (which would need
    a live JWKS server). The stub returns a fixed VerifiedPrincipal
    for any bearer token, letting the test exercise the full
    middleware + Depends + handler chain without crypto.
    """
    from dataclasses import replace
    from uuid import UUID

    from cora.infrastructure import deps as deps_module
    from cora.infrastructure.ports import VerifiedPrincipal

    verified_principal_id = UUID("01900000-0000-7000-8000-000000000d01")

    class _StubVerifier:
        async def verify(self, token: str, *, expected_audience: UUID) -> VerifiedPrincipal:
            _ = token, expected_audience  # accept any token
            return VerifiedPrincipal(
                principal_id=verified_principal_id,
                subject="user-test",
                issuer="https://idp.example.com",
                kind="human",
            )

    _original_build_kernel = deps_module.build_kernel

    async def _build_kernel_with_stub(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        kernel, teardown = await _original_build_kernel(*args, **kwargs)  # type: ignore[arg-type]
        # Swap the registry-built verifier for our stub (frozen
        # dataclass -> dataclasses.replace).
        return replace(kernel, token_verifier=_StubVerifier()), teardown

    monkeypatch.setattr(deps_module, "build_kernel", _build_kernel_with_stub)
    monkeypatch.setattr("cora.api.main.build_kernel", _build_kernel_with_stub)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IDENTITY_PROVIDERS", _IDPS_JSON)

    with TestClient(create_app()) as client:
        # Any bearer string works -- the stub returns the same
        # principal regardless of token value.
        response = client.post(
            "/actors",
            json={"name": "BearerUser"},
            headers={"Authorization": "Bearer any-token-the-stub-accepts"},
        )

    assert response.status_code == 201
    actor_id = UUID(response.json()["actor_id"])
    # Read back the ActorRegistered event and assert its principal_id
    # is the VERIFIED principal, NOT SYSTEM_PRINCIPAL_ID and NOT any
    # value the client could have controlled.
    deps = client.app.state.deps  # type: ignore[attr-defined]
    import asyncio

    events, _ = asyncio.run(deps.event_store.load("Actor", actor_id))
    assert len(events) == 1
    assert events[0].event_type == "ActorRegistered"
    # The load-bearing invariant: bearer-verified principal_id lands
    # on the persisted event's principal_id column.
    assert events[0].principal_id == verified_principal_id


@pytest.mark.contract
def test_x_principal_id_ignored_when_bearer_present_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end variant of the unit-tier `wins_over_x_principal_id`
    test: with BOTH a verified bearer AND an X-Principal-Id header,
    the persisted event carries the BEARER's principal_id, not the
    header's value. Pin: the silent-ignore design choice (Iter C-3
    Mode 1) holds through the full middleware -> Depends -> route
    chain."""
    from dataclasses import replace
    from uuid import UUID

    from cora.infrastructure import deps as deps_module
    from cora.infrastructure.ports import VerifiedPrincipal

    verified_principal_id = UUID("01900000-0000-7000-8000-000000000d02")
    spoofed_principal_id = UUID("01900000-0000-7000-8000-000000000d99")

    class _StubVerifier:
        async def verify(self, token: str, *, expected_audience: UUID) -> VerifiedPrincipal:
            _ = token, expected_audience
            return VerifiedPrincipal(
                principal_id=verified_principal_id,
                subject="user-test",
                issuer="https://idp.example.com",
                kind="human",
            )

    _original = deps_module.build_kernel

    async def _wrap(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        kernel, teardown = await _original(*args, **kwargs)  # type: ignore[arg-type]
        return replace(kernel, token_verifier=_StubVerifier()), teardown

    monkeypatch.setattr(deps_module, "build_kernel", _wrap)
    monkeypatch.setattr("cora.api.main.build_kernel", _wrap)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IDENTITY_PROVIDERS", _IDPS_JSON)

    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "BearerUser"},
            headers={
                "Authorization": "Bearer any",
                # Attempt to spoof a different principal via the
                # legacy cleartext header.
                "X-Principal-Id": str(spoofed_principal_id),
            },
        )

    assert response.status_code == 201
    actor_id = UUID(response.json()["actor_id"])
    deps = client.app.state.deps  # type: ignore[attr-defined]
    import asyncio

    events, _ = asyncio.run(deps.event_store.load("Actor", actor_id))
    # BEARER wins; X-Principal-Id silently ignored.
    assert events[0].principal_id == verified_principal_id
    assert events[0].principal_id != spoofed_principal_id
