"""Unit tests for `cora.api.mcp_principal.get_mcp_principal_id`.

Strategy: build a minimal fake `Context` whose `request_context.request`
is a programmable `_FakeRequest` carrying `.state.principal` (the
slot `BearerAuthMiddleware` stashes on) and `.app.state.deps`. Tests
exercise each of the 3 resolver modes without standing up a real
FastMCP server or Starlette app.

The contract tier covers the full FastMCP-streamable-http
round trip; here we pin the resolver's logic in isolation.
"""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from cora.infrastructure.mcp_principal import McpUnauthenticatedError, get_mcp_principal_id
from cora.infrastructure.ports import VerifiedPrincipal
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

_ISSUER = "https://idp.example.com"
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000000aa")


# ---------- Fake Context shape ----------


@dataclass
class _FakeDeps:
    token_verifier: Any = None


@dataclass
class _FakeAppState:
    deps: _FakeDeps | None = None


@dataclass
class _FakeApp:
    state: _FakeAppState = field(default_factory=_FakeAppState)


@dataclass
class _FakeRequestState:
    principal: Any = None


@dataclass
class _FakeRequest:
    state: _FakeRequestState = field(default_factory=_FakeRequestState)
    app: _FakeApp = field(default_factory=_FakeApp)


def _make_ctx(
    *,
    principal: Any = None,
    verifier_present: bool = False,
    request_missing: bool = False,
) -> Any:
    """Build a SimpleNamespace shaped like FastMCP's `Context`.

    `ctx.request_context.request.state.principal` is the slot the
    middleware writes on the happy path.
    `ctx.request_context.request.app.state.deps.token_verifier`
    decides bearer-auth-mode.
    """
    if request_missing:
        return SimpleNamespace(request_context=SimpleNamespace(request=None))

    request = _FakeRequest()
    request.state.principal = principal
    if verifier_present:
        request.app.state.deps = _FakeDeps(token_verifier=object())
    else:
        request.app.state.deps = _FakeDeps(token_verifier=None)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def _verified_principal() -> VerifiedPrincipal:
    return VerifiedPrincipal(
        principal_id=_PRINCIPAL_ID,
        subject="user-abc",
        issuer=_ISSUER,
        kind="human",
    )


# ---------- Mode 1: bearer-verified principal wins ----------


@pytest.mark.unit
def test_verified_principal_returns_its_principal_id() -> None:
    """Happy path. Middleware verified a bearer; resolver returns the
    VerifiedPrincipal.principal_id. Doesn't matter whether bearer-auth
    is "enabled" in the deps — if there's already a verified principal
    on request.state, that's authoritative."""
    ctx = _make_ctx(principal=_verified_principal(), verifier_present=True)
    assert get_mcp_principal_id(ctx) == _PRINCIPAL_ID


@pytest.mark.unit
def test_verified_principal_wins_even_when_verifier_not_present() -> None:
    """Defensive: even if app.state.deps.token_verifier is None, a
    `VerifiedPrincipal` on request.state is still authoritative.
    The verifier-presence flag is for Mode-2 logic only."""
    ctx = _make_ctx(principal=_verified_principal(), verifier_present=False)
    assert get_mcp_principal_id(ctx) == _PRINCIPAL_ID


# ---------- Mode 1 guard: non-VerifiedPrincipal duck-types rejected ----------


@pytest.mark.unit
def test_non_verified_principal_on_state_is_not_honored() -> None:
    """Isinstance guard: a future middleware that accidentally writes
    a duck-typed object with a `.principal_id` attribute to
    request.state.principal MUST NOT silently authenticate. Without
    bearer-auth enabled, this falls through to SYSTEM."""
    impostor = SimpleNamespace(principal_id=UUID("12345678-0000-0000-0000-000000000000"))
    ctx = _make_ctx(principal=impostor, verifier_present=False)
    # SYSTEM fallback applies (Mode 3); the impostor is ignored.
    assert get_mcp_principal_id(ctx) == SYSTEM_PRINCIPAL_ID


# ---------- Mode 2: bearer-auth enabled + no verified principal ----------


@pytest.mark.unit
def test_bearer_auth_enabled_with_no_principal_raises() -> None:
    """When deps.token_verifier is non-None but request.state has no
    VerifiedPrincipal, the resolver MUST refuse to fall back to
    SYSTEM. Raises McpUnauthenticatedError; FastMCP wraps as a
    structured JSON-RPC error response."""
    ctx = _make_ctx(principal=None, verifier_present=True)
    with pytest.raises(McpUnauthenticatedError):
        get_mcp_principal_id(ctx)


# ---------- Mode 3: legacy fallback ----------


@pytest.mark.unit
def test_legacy_mode_with_no_principal_returns_system_principal_id() -> None:
    """No verifier configured, no verified principal: dev / test posture.
    Returns SYSTEM_PRINCIPAL_ID. Production deployments configure IdPs
    and run with require_authenticated_principal=True so this branch
    is unreachable in prod."""
    ctx = _make_ctx(principal=None, verifier_present=False)
    assert get_mcp_principal_id(ctx) == SYSTEM_PRINCIPAL_ID


# ---------- Defensive: stdio / no-request paths ----------


@pytest.mark.unit
def test_missing_request_falls_back_to_system_principal() -> None:
    """When `ctx.request_context.request` is None (stdio transport,
    no HTTP request frame), the resolver treats it as legacy mode and
    returns SYSTEM. AH13: MCP_STDIO is not bearer-verified."""
    ctx = _make_ctx(request_missing=True)
    assert get_mcp_principal_id(ctx) == SYSTEM_PRINCIPAL_ID


@pytest.mark.unit
def test_no_request_context_attribute_falls_back_safely() -> None:
    """If a future FastMCP version restructures and `ctx.request_context`
    is missing entirely, the resolver MUST NOT crash — it falls back
    to SYSTEM in dev/test (where this branch is reachable) and raises
    in prod via the verifier-presence path on the next call."""
    ctx = SimpleNamespace()  # no `request_context` attribute at all
    # No request -> no verifier-presence check possible -> SYSTEM fallback.
    # In a prod deployment this is benign because bearer-auth posture
    # requires a verifier (which lives off the absent request).
    assert get_mcp_principal_id(ctx) == SYSTEM_PRINCIPAL_ID
