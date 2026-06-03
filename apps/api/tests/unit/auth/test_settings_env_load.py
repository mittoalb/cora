"""Unit tests for env-var → `Settings.identity_providers` JSON round-trip.

Gap surfaced at the gate review (test-coverage #1+#2,
design #12): every existing test constructs Settings programmatically
with `Settings(identity_providers=[...])`, bypassing the
pydantic-settings JSON parsing path entirely. This module exercises
the actual deployment surface — `IDENTITY_PROVIDERS='[{...JSON...}]'`
env var loaded by Settings(no args) — so the failure mode that bites
operators on first prod deploy is pinned by CI.
"""

import json

import pytest

from cora.infrastructure.auth.config import IdentityProviderConfig
from cora.infrastructure.config import Settings


@pytest.mark.unit
def test_identity_providers_env_var_loads_single_jwt_idp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `IDENTITY_PROVIDERS` env var carries a JSON list of
    IdentityProviderConfig dicts; pydantic-settings parses, validates,
    and exposes them on `Settings().identity_providers`."""
    payload = json.dumps(
        [
            {
                "issuer": "https://idp.example.com",
                "jwks_url": "https://idp.example.com/jwks",
                "audiences": {
                    "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                },
                "allowed_algorithms": ["RS256"],
            }
        ]
    )
    monkeypatch.setenv("IDENTITY_PROVIDERS", payload)
    settings = Settings()  # type: ignore[call-arg]
    assert len(settings.identity_providers) == 1
    idp = settings.identity_providers[0]
    assert isinstance(idp, IdentityProviderConfig)
    assert idp.issuer == "https://idp.example.com"
    assert idp.jwks_url == "https://idp.example.com/jwks"
    assert idp.allowed_algorithms == ["RS256"]


@pytest.mark.unit
def test_identity_providers_env_var_wraps_client_secret_in_secretstr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SecretStr round-trip: the env-var-loaded `introspection_client_secret`
    MUST be wrapped in `SecretStr` (not stored as plain str). Verify by
    asserting `repr(settings)` doesn't contain the secret value."""
    payload = json.dumps(
        [
            {
                "issuer": "https://idp.example.com",
                "introspection_url": "https://idp.example.com/introspect",
                "introspection_client_id": "cora-rs",
                "introspection_client_secret": "super-secret-value-12345",
                "audiences": {
                    "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                },
            }
        ]
    )
    monkeypatch.setenv("IDENTITY_PROVIDERS", payload)
    settings = Settings()  # type: ignore[call-arg]
    idp = settings.identity_providers[0]
    # The constructed model has a SecretStr field — its `.get_secret_value()`
    # returns the actual secret, and its `__str__` / `__repr__` redact.
    assert idp.introspection_client_secret is not None
    assert idp.introspection_client_secret.get_secret_value() == "super-secret-value-12345"
    assert "super-secret-value-12345" not in repr(idp)
    assert "super-secret-value-12345" not in repr(settings)
    assert "super-secret-value-12345" not in settings.model_dump_json()


@pytest.mark.unit
def test_identity_providers_env_var_loads_multiple_idps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mainstream deployment shape: multiple JWT IdPs + one Globus
    introspection IdP. Roundtrip the whole list intact."""
    payload = json.dumps(
        [
            {
                "issuer": "https://entra.microsoftonline.com",
                "jwks_url": "https://login.microsoftonline.com/jwks",
                "audiences": {
                    "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                },
            },
            {
                "issuer": "https://auth.globus.org",
                "introspection_url": "https://auth.globus.org/v2/oauth2/token/introspect",
                "introspection_client_id": "cora-rs",
                "introspection_client_secret": "globus-rs-secret",
                "audiences": {
                    "00000000-0000-0000-0000-000000000022": "https://cora.example/mcp",
                },
            },
        ]
    )
    monkeypatch.setenv("IDENTITY_PROVIDERS", payload)
    settings = Settings()  # type: ignore[call-arg]
    assert len(settings.identity_providers) == 2
    assert settings.identity_providers[0].issuer == "https://entra.microsoftonline.com"
    assert settings.identity_providers[1].issuer == "https://auth.globus.org"


@pytest.mark.unit
def test_identity_providers_env_var_validation_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed entry (for example neither jwks_url nor introspection_url)
    raises ValidationError at `Settings()` construction — not at first
    auth attempt. Operators see the failure at boot."""
    payload = json.dumps(
        [
            {
                "issuer": "https://broken.example.com",
                "audiences": {
                    "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                },
                # No jwks_url, no introspection_url
            }
        ]
    )
    monkeypatch.setenv("IDENTITY_PROVIDERS", payload)
    with pytest.raises(Exception, match=r"jwks_url|introspection_url"):
        Settings()  # type: ignore[call-arg]


@pytest.mark.unit
def test_empty_audiences_in_env_var_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate-review F12: empty `audiences = {}` is now a validation
    error at boot, not a fail-late at first request."""
    payload = json.dumps(
        [
            {
                "issuer": "https://idp.example.com",
                "jwks_url": "https://idp.example.com/jwks",
                "audiences": {},
            }
        ]
    )
    monkeypatch.setenv("IDENTITY_PROVIDERS", payload)
    with pytest.raises(Exception, match=r"audiences map must have"):
        Settings()  # type: ignore[call-arg]
