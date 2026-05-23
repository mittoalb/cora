"""Unit tests for `cora.infrastructure.routing`.

Direct invocation of the FastAPI dependency function; the
`x_principal_id` parameter is what FastAPI's `Header(...)` machinery
passes at request time. We test that:
  - Header value (UUID) is returned as-is.
  - Header absent (None) falls back to `SYSTEM_PRINCIPAL_ID`.
  - The function trusts the header value (no actor-existence check).

Pydantic UUID-format validation happens BEFORE this function runs
(FastAPI's request layer); contract tests cover the malformed-header
422 path end-to-end.

Replaces the per-BC `tests/unit/<bc>/test_routing.py` files that
existed pre-cleanup, when each BC owned its own `_routing.py`. Both
BCs now import the same canonical implementation from infrastructure.
"""

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID, get_principal_id


@pytest.mark.unit
def test_get_principal_id_returns_header_uuid_when_present() -> None:
    pid = uuid4()
    assert get_principal_id(x_principal_id=pid) == pid


@pytest.mark.unit
def test_get_principal_id_falls_back_to_system_when_header_absent() -> None:
    """Legacy fallback semantics preserved: existing tests + dev calls
    that don't set the header continue to use SYSTEM_PRINCIPAL_ID."""
    assert get_principal_id(x_principal_id=None) == SYSTEM_PRINCIPAL_ID


@pytest.mark.unit
def test_get_principal_id_does_not_validate_principal_existence() -> None:
    """The function trusts the header value as-is (trust-the-proxy
    pattern). It does NOT verify that the UUID corresponds to a
    registered Actor — that's a Trust-BC concern at the Authorize
    gate. Pinned so a future "validate principal exists" check has
    to do so deliberately at the right layer."""
    arbitrary = UUID("01900000-0000-7000-8000-000000007777")
    assert get_principal_id(x_principal_id=arbitrary) == arbitrary


@pytest.mark.unit
def test_system_principal_id_is_the_well_known_zero_uuid() -> None:
    """Pin the canonical fallback value. Changing it would silently
    invalidate every running deployment's Policy entries that
    reference SYSTEM_PRINCIPAL_ID, so the change must be deliberate."""
    assert UUID("00000000-0000-0000-0000-000000000000") == SYSTEM_PRINCIPAL_ID


# ---------- Bearer-mode priority ----------


@pytest.mark.unit
def test_bearer_principal_id_wins_over_x_principal_id_header() -> None:
    """When BearerAuthMiddleware has stashed a VerifiedPrincipal on
    request.state, `get_principal_id` returns its principal_id even
    if the legacy X-Principal-Id header is ALSO present. Pins the
    no-fallback-via-cleartext invariant: a verified bearer always
    wins; the cleartext header is silently ignored under bearer-auth
    mode so a misconfigured client doesn't accidentally elevate."""
    bearer_id = UUID("01900000-0000-7000-8000-000000000b01")
    header_id = UUID("01900000-0000-7000-8000-000000000b02")
    assert (
        get_principal_id(
            x_principal_id=header_id,
            bearer_principal_id=bearer_id,
            bearer_auth_enabled=True,
        )
        == bearer_id
    )


@pytest.mark.unit
def test_bearer_auth_enabled_without_bearer_raises_401_with_www_authenticate() -> None:
    """When `kernel.token_verifier` is wired (bearer-auth mode) and no
    bearer was verified, the X-Principal-Id fallback is NOT allowed.
    `get_principal_id` raises HTTP 401 with the RFC 6750 §3
    `WWW-Authenticate: Bearer` challenge pointing at the RFC 9728
    protected-resource metadata endpoint."""
    with pytest.raises(HTTPException) as exc:
        get_principal_id(
            x_principal_id=None,
            bearer_principal_id=None,
            bearer_auth_enabled=True,
        )
    assert exc.value.status_code == 401
    # The challenge MUST carry the WWW-Authenticate header per RFC 6750.
    assert exc.value.headers is not None
    assert "WWW-Authenticate" in exc.value.headers
    assert exc.value.headers["WWW-Authenticate"].startswith("Bearer ")
    assert "/.well-known/oauth-protected-resource" in exc.value.headers["WWW-Authenticate"]


@pytest.mark.unit
def test_bearer_auth_enabled_rejects_x_principal_id_fallback() -> None:
    """Even with X-Principal-Id PRESENT, bearer-auth mode without a
    verified bearer rejects the request. The cleartext header is
    unauthenticated; honoring it would let a client downgrade past
    the bearer gate by sending only X-Principal-Id."""
    header_id = UUID("01900000-0000-7000-8000-000000000b03")
    with pytest.raises(HTTPException) as exc:
        get_principal_id(
            x_principal_id=header_id,
            bearer_principal_id=None,
            bearer_auth_enabled=True,
        )
    assert exc.value.status_code == 401


@pytest.mark.unit
def test_legacy_mode_unchanged_when_bearer_auth_disabled() -> None:
    """`bearer_auth_enabled=False` (no IdPs configured) preserves the
    legacy X-Principal-Id-with-SYSTEM-fallback shape. Existing
    tests + deployments that never set IDENTITY_PROVIDERS remain on
    the legacy path unchanged."""
    # Header present + no bearer + legacy mode -> return header value.
    pid = uuid4()
    assert (
        get_principal_id(
            x_principal_id=pid,
            bearer_principal_id=None,
            bearer_auth_enabled=False,
        )
        == pid
    )
    # Header absent + no bearer + legacy mode + require=False -> SYSTEM.
    assert (
        get_principal_id(
            x_principal_id=None,
            bearer_principal_id=None,
            bearer_auth_enabled=False,
            require_authenticated=False,
        )
        == SYSTEM_PRINCIPAL_ID
    )


@pytest.mark.unit
def test_legacy_mode_require_authenticated_raises_401_without_www_authenticate() -> None:
    """Phase-3e legacy 401: `require_authenticated_principal=True`
    with no header still raises 401 — but with the LEGACY error
    message (no WWW-Authenticate header, since this isn't a bearer
    challenge). Pins the two 401 paths stay distinguishable in logs
    + client behavior."""
    with pytest.raises(HTTPException) as exc:
        get_principal_id(
            x_principal_id=None,
            bearer_principal_id=None,
            bearer_auth_enabled=False,
            require_authenticated=True,
        )
    assert exc.value.status_code == 401
    # Legacy path: no WWW-Authenticate (not a bearer challenge).
    assert exc.value.headers is None or "WWW-Authenticate" not in (exc.value.headers or {})
