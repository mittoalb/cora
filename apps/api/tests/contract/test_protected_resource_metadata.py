"""Contract tests for `GET /.well-known/oauth-protected-resource`.

Per MCP spec 2025-11-25 (basic/authorization) + RFC 9728, MCP-aware
OAuth clients dereference this endpoint after a 401 response to
discover which authorization servers to obtain a token from. The
response is JSON; required keys per RFC 9728 §3:
  - `resource` (URI of the resource server)
  - `authorization_servers` (array of issuer URLs)

CORA extensions:
  - `x-cora-surface-audiences` — per-Surface audience map
  - `bearer_methods_supported` — `["header"]` (CORA only accepts
    `Authorization: Bearer`)
"""

from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cora.api.main import create_app
from cora.infrastructure.auth.config import IdentityProviderConfig
from cora.infrastructure.config import Settings

_HTTP_SURFACE = UUID("00000000-0000-0000-0000-000000000020")
_MCP_SURFACE = UUID("00000000-0000-0000-0000-000000000022")


@pytest.mark.contract
def test_metadata_endpoint_returns_200_with_required_keys() -> None:
    """Empty identity_providers list still serves a valid (if minimal)
    metadata document. Required RFC 9728 keys present."""
    with TestClient(create_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    assert response.status_code == 200
    body = response.json()
    assert "resource" in body
    assert "authorization_servers" in body
    assert isinstance(body["authorization_servers"], list)
    assert body["bearer_methods_supported"] == ["header"]


@pytest.mark.contract
def test_metadata_includes_cache_control_header() -> None:
    """Clients SHOULD cache the metadata; default 5-minute cache window
    keeps cold-start IdP-discovery cheap."""
    with TestClient(create_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    assert "max-age" in response.headers.get("Cache-Control", "")


@pytest.mark.contract
def test_metadata_lists_configured_authorization_servers() -> None:
    """When identity_providers are configured, their issuers appear in
    `authorization_servers` (RFC 8414 dereferencing target)."""
    settings = Settings(  # type: ignore[call-arg]
        app_env="test",
        identity_providers=[
            IdentityProviderConfig(
                issuer="https://idp-a.example.com",
                jwks_url="https://idp-a.example.com/jwks",
                audiences={_HTTP_SURFACE: "https://cora.test/http"},
            ),
            IdentityProviderConfig(
                issuer="https://idp-b.example.com",
                introspection_url="https://idp-b.example.com/introspect",
                introspection_client_id="cora-rs",
                introspection_client_secret=SecretStr("secret"),
                audiences={_MCP_SURFACE: "https://cora.test/mcp"},
            ),
        ],
    )
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    body = response.json()
    assert "https://idp-a.example.com" in body["authorization_servers"]
    assert "https://idp-b.example.com" in body["authorization_servers"]


@pytest.mark.contract
def test_metadata_exposes_per_surface_audiences() -> None:
    """CORA extension: clients that recognize the Surface model can
    pick the right `aud` per Surface without out-of-band knowledge."""
    settings = Settings(  # type: ignore[call-arg]
        app_env="test",
        identity_providers=[
            IdentityProviderConfig(
                issuer="https://idp-a.example.com",
                jwks_url="https://idp-a.example.com/jwks",
                audiences={
                    _HTTP_SURFACE: "https://cora.test/http",
                    _MCP_SURFACE: "https://cora.test/mcp",
                },
            ),
        ],
    )
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    body = response.json()
    assert body["io.cora.surface_audiences"]["http"] == "https://cora.test/http"
    assert body["io.cora.surface_audiences"]["mcp_streamable_http"] == "https://cora.test/mcp"


@pytest.mark.contract
def test_metadata_resource_field_matches_request_host() -> None:
    """RFC 9728 §3.1: `resource` value SHOULD be the canonical URL.
    We derive it from the inbound request host so the same deployment
    serving multiple hostnames returns the right value per request."""
    with TestClient(create_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    body = response.json()
    # TestClient defaults to http://testserver.
    assert body["resource"] == "http://testserver"


@pytest.mark.contract
def test_metadata_endpoint_unauthenticated() -> None:
    """The metadata endpoint MUST be reachable without authentication —
    it's how clients discover the auth flow in the first place. Even
    with require_authenticated_principal=True, this endpoint is open."""
    settings = Settings(  # type: ignore[call-arg]
        app_env="test",
        require_authenticated_principal=True,  # production posture (test#7 polarity)
    )
    with TestClient(create_app(settings=settings)) as client:
        response = client.get(
            "/.well-known/oauth-protected-resource",
            # NO Authorization header, NO X-Principal-Id — pure
            # unauthenticated probe.
        )
    assert response.status_code == 200


# ---------- gate-review additions ----------


@pytest.mark.contract
def test_metadata_uses_extension_key_without_x_prefix() -> None:
    """Gate-review security F10: RFC 6648 (2012) deprecated the `X-` /
    `x-` prefix convention. An earlier draft used `x-cora-...`;
    renamed to a reverse-DNS namespace key without prefix."""
    with TestClient(create_app()) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    body = response.json()
    assert "x-cora-surface-audiences" not in body, "must not use deprecated x- prefix"
    assert "io.cora.surface_audiences" in body


@pytest.mark.contract
def test_metadata_resource_honors_x_forwarded_headers() -> None:
    """Gate-review test#6 + security F4: behind a reverse proxy
    (the production deployment shape) the metadata endpoint must
    derive `resource` from X-Forwarded-Proto + X-Forwarded-Host so
    the document points at the public URL, not the internal pod."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/.well-known/oauth-protected-resource",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "aps-35bm.cora.example",
            },
        )
    body = response.json()
    assert body["resource"] == "https://aps-35bm.cora.example"


@pytest.mark.contract
def test_settings_injection_propagates_to_app_state() -> None:
    """Gate-review test#8: pin that the `settings=` kwarg actually
    reaches `app.state.deps.settings`. Without this, an env-var
    pre-set in CI could silently mask the test override."""
    settings = Settings(  # type: ignore[call-arg]
        app_env="test",
        identity_providers=[
            IdentityProviderConfig(
                issuer="https://injected.example.com",
                jwks_url="https://injected.example.com/jwks",
                audiences={_HTTP_SURFACE: "https://cora.injected/http"},
            ),
        ],
    )
    with TestClient(create_app(settings=settings)) as client:
        deps_settings: Settings = client.app.state.deps.settings  # type: ignore[attr-defined]
        assert deps_settings is settings, "settings= kwarg did not propagate"
        # pydantic-settings type inference loses generic info on
        # list[IdentityProviderConfig]; assert via cast for pyright.
        raw_idps = cast("list[IdentityProviderConfig]", deps_settings.identity_providers)  # pyright: ignore[reportUnknownMemberType]
        assert raw_idps[0].issuer == "https://injected.example.com"


@pytest.mark.contract
def test_metadata_last_wins_when_two_idps_declare_same_surface() -> None:
    """Gate-review test#3: pin the multi-IdP-same-Surface contract.
    Today the handler iterates identity_providers and overwrites,
    so the LAST IdP's audience for a given Surface survives. This
    test locks the current behavior so a future change to for example
    raise-on-collision is explicit and intentional."""
    settings = Settings(  # type: ignore[call-arg]
        app_env="test",
        identity_providers=[
            IdentityProviderConfig(
                issuer="https://idp-a.example.com",
                jwks_url="https://idp-a.example.com/jwks",
                audiences={_HTTP_SURFACE: "https://first.example/http"},
            ),
            IdentityProviderConfig(
                issuer="https://idp-b.example.com",
                jwks_url="https://idp-b.example.com/jwks",
                audiences={_HTTP_SURFACE: "https://second.example/http"},
            ),
        ],
    )
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/.well-known/oauth-protected-resource")
    body = response.json()
    # CURRENT contract: last-iterated wins. If future iteration adds
    # raise-on-collision, this test gets flipped to pytest.raises.
    assert body["io.cora.surface_audiences"]["http"] == "https://second.example/http", (
        "current contract is last-wins; update intentionally if changing"
    )
