"""Unit tests for `cora.infrastructure.auth.build_idp_registry.build_idp_registry`.

Pins config-row → adapter-instance translation. The adapter
construction itself is exercised end-to-end by the existing
JWT/Introspection/Registry tests; here we focus on:
  - empty list → None (legacy path)
  - JWT-only IdP → 1 JwtTokenVerifier
  - introspection-only IdP → 1 IntrospectionTokenVerifier
  - both-paths IdP → 1 JwtTokenVerifier + 1 IntrospectionTokenVerifier
  - multi-JWT-IdP → registry routes by issuer
  - multi-introspection-IdP → ValueError
"""

from uuid import UUID

import pytest
from pydantic import SecretStr

from cora.infrastructure.auth.build_idp_registry import build_idp_registry
from cora.infrastructure.auth.config import IdentityProviderConfig, StaticSubjectMapper
from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
from tests.unit.auth._helpers import TEST_AUD_HTTP, TEST_SURFACE_HTTP

_MAPPER = StaticSubjectMapper({})


def _jwt_config(issuer: str) -> IdentityProviderConfig:
    return IdentityProviderConfig(
        issuer=issuer,
        jwks_url="https://example.com/jwks",
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )


def _introspection_config(issuer: str) -> IdentityProviderConfig:
    return IdentityProviderConfig(
        issuer=issuer,
        introspection_url="https://example.com/introspect",
        introspection_client_id="cora-rs",
        introspection_client_secret=SecretStr("secret"),
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )


@pytest.mark.unit
def test_empty_list_returns_none() -> None:
    """Legacy path: empty config → registry None → middleware falls
    through to X-Principal-Id."""
    assert build_idp_registry([], subject_mapper=_MAPPER) is None


@pytest.mark.unit
def test_single_jwt_config_builds_registry() -> None:
    registry = build_idp_registry(
        [_jwt_config("https://idp-a.example.com")],
        subject_mapper=_MAPPER,
    )
    assert isinstance(registry, IdentityProviderRegistry)


@pytest.mark.unit
def test_single_introspection_config_builds_registry() -> None:
    registry = build_idp_registry(
        [_introspection_config("https://opaque-idp.example.com")],
        subject_mapper=_MAPPER,
    )
    assert isinstance(registry, IdentityProviderRegistry)


@pytest.mark.unit
def test_both_paths_config_constructs_two_adapters() -> None:
    """A single IdP with both JWT and introspection produces both
    adapter types in one registry."""
    cfg = IdentityProviderConfig(
        issuer="https://dual.example.com",
        jwks_url="https://dual.example.com/jwks",
        introspection_url="https://dual.example.com/introspect",
        introspection_client_id="cora-rs",
        introspection_client_secret=SecretStr("secret"),
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )
    registry = build_idp_registry([cfg], subject_mapper=_MAPPER)
    assert isinstance(registry, IdentityProviderRegistry)
    # Gate-review test#10: assert internal shape, not just isinstance.
    assert len(registry._jwt_by_issuer) == 1  # type: ignore[attr-defined]
    assert "https://dual.example.com" in registry._jwt_by_issuer  # type: ignore[attr-defined]
    assert registry._introspection is not None  # type: ignore[attr-defined]
    assert registry._introspection.issuer == "https://dual.example.com"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_multiple_jwt_idps_allowed() -> None:
    """Many JWT IdPs is fine — the registry routes by token's `iss`."""
    registry = build_idp_registry(
        [
            _jwt_config("https://idp-a.example.com"),
            _jwt_config("https://idp-b.example.com"),
            _jwt_config("https://idp-c.example.com"),
        ],
        subject_mapper=_MAPPER,
    )
    assert isinstance(registry, IdentityProviderRegistry)


@pytest.mark.unit
def test_multiple_introspection_idps_rejected() -> None:
    """Narrow contract: only one introspection IdP per
    deployment (the registry's opaque-token routing can't disambiguate)."""
    with pytest.raises(ValueError, match=r"more than one.*introspection_url"):
        build_idp_registry(
            [
                _introspection_config("https://opaque-a.example.com"),
                _introspection_config("https://opaque-b.example.com"),
            ],
            subject_mapper=_MAPPER,
        )


@pytest.mark.unit
def test_mixed_jwt_and_single_introspection_allowed() -> None:
    """Multiple JWT IdPs + one introspection IdP (the realistic shape
    for a deployment with mainstream IdPs + Globus)."""
    registry = build_idp_registry(
        [
            _jwt_config("https://entra.example.com"),
            _jwt_config("https://orcid.example.com"),
            _introspection_config("https://auth.globus.org"),
        ],
        subject_mapper=_MAPPER,
    )
    assert isinstance(registry, IdentityProviderRegistry)


@pytest.mark.unit
def test_introspection_creds_unwrapped_for_basic_auth() -> None:
    """The SecretStr from Settings reaches the IntrospectionTokenVerifier
    constructor — which accepts both raw str AND SecretStr — and gets
    stored as SecretStr internally (gate-review F6)."""
    cfg = IdentityProviderConfig(
        issuer="https://opaque.example.com",
        introspection_url="https://opaque.example.com/introspect",
        introspection_client_id="cora-rs",
        introspection_client_secret=SecretStr("hidden-secret"),
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )
    registry = build_idp_registry([cfg], subject_mapper=_MAPPER)
    assert isinstance(registry, IdentityProviderRegistry)
    assert "hidden-secret" not in repr(vars(registry))


# Forward-compat: a UUID literal used in surface mappings must round-trip
# through pydantic-settings JSON parsing. Sanity-check on the type.
@pytest.mark.unit
def test_uuid_keys_in_audiences_round_trip() -> None:
    surface_uuid = UUID("00000000-0000-0000-0000-000000000020")
    cfg = IdentityProviderConfig(
        issuer="https://idp.example.com",
        jwks_url="https://idp.example.com/jwks",
        audiences={surface_uuid: "https://cora.example/http"},
    )
    assert surface_uuid in cfg.audiences
    assert cfg.audiences[surface_uuid] == "https://cora.example/http"
