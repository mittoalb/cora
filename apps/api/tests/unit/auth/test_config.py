"""Unit tests for `cora.infrastructure.auth.config`.

Pins the IdentityProviderConfig Pydantic schema + StaticSubjectMapper.
"""

from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from cora.infrastructure.auth.config import IdentityProviderConfig, StaticSubjectMapper
from cora.infrastructure.ports.token_verifier import InvalidTokenError
from tests.unit.auth._helpers import TEST_AUD_HTTP, TEST_ISSUER, TEST_SURFACE_HTTP

# ---------- IdentityProviderConfig ----------


@pytest.mark.unit
def test_jwt_only_config_is_valid() -> None:
    cfg = IdentityProviderConfig(
        issuer=TEST_ISSUER,
        jwks_url="https://idp.example.com/jwks",
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )
    assert cfg.jwks_url == "https://idp.example.com/jwks"
    assert cfg.introspection_url is None
    assert cfg.algorithms_allowed == ["RS256", "ES256"]
    assert cfg.principal_kind == "human"


@pytest.mark.unit
def test_introspection_only_config_is_valid() -> None:
    cfg = IdentityProviderConfig(
        issuer=TEST_ISSUER,
        introspection_url="https://idp.example.com/introspect",
        introspection_client_id="cora-rs",
        introspection_client_secret=SecretStr("secret"),
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )
    assert cfg.introspection_url == "https://idp.example.com/introspect"
    assert cfg.jwks_url is None


@pytest.mark.unit
def test_both_paths_config_is_valid() -> None:
    """A single IdP can opt into both JWT and introspection (e.g. fast
    JWT verify normally + introspection for revocation-sensitive callers)."""
    cfg = IdentityProviderConfig(
        issuer=TEST_ISSUER,
        jwks_url="https://idp.example.com/jwks",
        introspection_url="https://idp.example.com/introspect",
        introspection_client_id="cora-rs",
        introspection_client_secret=SecretStr("secret"),
        audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
    )
    assert cfg.jwks_url is not None
    assert cfg.introspection_url is not None


@pytest.mark.unit
def test_config_without_any_verification_path_rejected() -> None:
    with pytest.raises(ValidationError, match=r"jwks_url.*OR.*introspection_url"):
        IdentityProviderConfig(
            issuer=TEST_ISSUER,
            audiences={TEST_SURFACE_HTTP: TEST_AUD_HTTP},
        )


@pytest.mark.unit
def test_introspection_url_without_credentials_rejected() -> None:
    with pytest.raises(
        ValidationError, match=r"introspection_client_id.*introspection_client_secret"
    ):
        IdentityProviderConfig(
            issuer=TEST_ISSUER,
            introspection_url="https://idp.example.com/introspect",
            # Missing client_id + secret.
        )


@pytest.mark.unit
def test_introspection_cache_ttl_floor() -> None:
    with pytest.raises(ValidationError):
        IdentityProviderConfig(
            issuer=TEST_ISSUER,
            introspection_url="https://idp.example.com/introspect",
            introspection_client_id="cora-rs",
            introspection_client_secret=SecretStr("secret"),
            introspection_cache_ttl_seconds=0,
        )


@pytest.mark.unit
def test_client_secret_never_in_repr() -> None:
    """SecretStr (Pydantic) redacts secrets in __repr__ + model_dump."""
    cfg = IdentityProviderConfig(
        issuer=TEST_ISSUER,
        introspection_url="https://idp.example.com/introspect",
        introspection_client_id="cora-rs",
        introspection_client_secret=SecretStr("super-secret-value"),
    )
    assert "super-secret-value" not in repr(cfg)
    assert "super-secret-value" not in cfg.model_dump_json()


# ---------- StaticSubjectMapper ----------


@pytest.mark.unit
async def test_static_mapper_returns_bound_actor() -> None:
    actor_id = UUID("01900000-0000-7000-8000-000000000099")
    mapper = StaticSubjectMapper({(TEST_ISSUER, "user-abc"): (actor_id, "human")})
    result_id, kind = await mapper(TEST_ISSUER, "user-abc")
    assert result_id == actor_id
    assert kind == "human"


@pytest.mark.unit
async def test_static_mapper_returns_service_account_kind() -> None:
    actor_id = UUID("01900000-0000-7000-8000-0000000000aa")
    mapper = StaticSubjectMapper({(TEST_ISSUER, "ci-bot"): (actor_id, "service_account")})
    _, kind = await mapper(TEST_ISSUER, "ci-bot")
    assert kind == "service_account"


@pytest.mark.unit
async def test_static_mapper_unknown_subject_raises() -> None:
    """A subject not in the binding map raises InvalidTokenError per
    the design memo's `unknown_subject` reason code."""
    mapper = StaticSubjectMapper({})
    with pytest.raises(InvalidTokenError) as exc:
        await mapper(TEST_ISSUER, "ghost-user")
    assert exc.value.reason == "unknown_subject"


@pytest.mark.unit
async def test_static_mapper_namespace_by_issuer() -> None:
    """The same subject id from different issuers maps to different
    Actors — defense against the same `sub` string in two IdPs."""
    actor_a = UUID("01900000-0000-7000-8000-000000000001")
    actor_b = UUID("01900000-0000-7000-8000-000000000002")
    mapper = StaticSubjectMapper(
        {
            ("https://idp-a.example.com", "shared-sub"): (actor_a, "human"),
            ("https://idp-b.example.com", "shared-sub"): (actor_b, "human"),
        }
    )
    a_id, _ = await mapper("https://idp-a.example.com", "shared-sub")
    b_id, _ = await mapper("https://idp-b.example.com", "shared-sub")
    assert a_id == actor_a
    assert b_id == actor_b
