"""Unit tests for `surface_context` structlog contextvars binding.

Pins the helper module's contract:

  - `bind_surface_context` stringifies the UUID and uses the kind
    string as-is, both bound on the structlog contextvars scope so
    `merge_contextvars` lifts them onto every log line.
  - `clear_surface_context` removes both keys; idempotent on missing.
  - `surface_kind_for` returns the mapped kind string for HTTP-reachable
    Surface UUIDs and raises `UnknownSurfaceError` otherwise.
  - The bind/clear pair leaves NO contextvars residue between
    invocations (catches missing-clear in middleware refactors).

Integration with `BearerAuthMiddleware` is exercised separately in
`tests/unit/auth/test_bearer_auth_middleware.py` once the binding
seam is in place; here we cover the helper in isolation against a
real structlog contextvars scope.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from collections.abc import Iterator
from uuid import UUID

import pytest
import structlog
from structlog.contextvars import get_contextvars

from cora.infrastructure.observability.surface_context import (
    SURFACE_KIND_HTTP,
    SURFACE_KIND_MCP_STREAMABLE_HTTP,
    UnknownSurfaceError,
    bind_surface_context,
    clear_surface_context,
    surface_kind_for,
)
from cora.infrastructure.routing import (
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STDIO_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
)


@pytest.fixture(autouse=True)
def clear_contextvars_before_and_after() -> Iterator[None]:
    """Each test starts and ends with a clean structlog contextvars scope.

    Other tests in the suite might bind contextvars without unbinding;
    we clear before + after so this file's assertions are deterministic
    no matter the collection order.
    """
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


@pytest.mark.unit
def test_bind_surface_context_stores_stringified_uuid_and_kind_on_contextvars() -> None:
    """Both keys land on the structlog contextvars scope; UUID is
    stringified so the JSONRenderer emits a stable shape, kind is
    passed through verbatim."""
    bind_surface_context(SYSTEM_HTTP_SURFACE_ID, SURFACE_KIND_HTTP)

    bound = get_contextvars()
    assert bound["surface_id"] == str(SYSTEM_HTTP_SURFACE_ID)
    assert bound["surface_kind"] == SURFACE_KIND_HTTP


@pytest.mark.unit
def test_bind_surface_context_overwrites_prior_binding_for_same_request() -> None:
    """Re-binding within the same scope replaces the previous values.
    Matches Starlette's per-request middleware semantics."""
    bind_surface_context(SYSTEM_HTTP_SURFACE_ID, SURFACE_KIND_HTTP)
    bind_surface_context(SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID, SURFACE_KIND_MCP_STREAMABLE_HTTP)

    bound = get_contextvars()
    assert bound["surface_id"] == str(SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID)
    assert bound["surface_kind"] == SURFACE_KIND_MCP_STREAMABLE_HTTP


@pytest.mark.unit
def test_clear_surface_context_removes_both_keys() -> None:
    """After clear, neither key remains on the scope. The middleware's
    `finally` block relies on this to prevent cross-request leakage."""
    bind_surface_context(SYSTEM_HTTP_SURFACE_ID, SURFACE_KIND_HTTP)
    clear_surface_context()

    bound = get_contextvars()
    assert "surface_id" not in bound
    assert "surface_kind" not in bound


@pytest.mark.unit
def test_clear_surface_context_is_safe_to_call_when_nothing_bound() -> None:
    """Idempotent: calling clear before any bind must not raise. Defensive
    so the middleware's `finally` block is safe even if `bind` was
    never reached (early exception)."""
    clear_surface_context()
    bound = get_contextvars()
    assert "surface_id" not in bound
    assert "surface_kind" not in bound


@pytest.mark.unit
def test_surface_kind_for_returns_http_for_system_http_surface() -> None:
    assert surface_kind_for(SYSTEM_HTTP_SURFACE_ID) == SURFACE_KIND_HTTP


@pytest.mark.unit
def test_surface_kind_for_returns_mcp_streamable_for_system_mcp_streamable_surface() -> None:
    assert (
        surface_kind_for(SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID) == SURFACE_KIND_MCP_STREAMABLE_HTTP
    )


@pytest.mark.unit
def test_surface_kind_for_raises_on_unknown_surface_uuid() -> None:
    """Loud-fail: an unmapped Surface UUID is a deploy-time bug. Silent
    fallback to a sentinel kind would let the observability dimension
    drift out of step with the seeded Surfaces."""
    unknown = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    with pytest.raises(UnknownSurfaceError):
        surface_kind_for(unknown)


@pytest.mark.unit
def test_surface_kind_for_raises_on_stdio_surface_excluded_from_http_map() -> None:
    """Stdio MCP is a subprocess transport that never flows through the
    HTTP middleware; its UUID is intentionally excluded from
    `_SURFACE_KIND_BY_UUID`. Calling the HTTP-side helper with the
    stdio UUID raises so a future code path that wires it incorrectly
    is caught immediately."""
    with pytest.raises(UnknownSurfaceError):
        surface_kind_for(SYSTEM_MCP_STDIO_SURFACE_ID)


@pytest.mark.unit
def test_back_to_back_bind_and_clear_cycles_leave_no_residue() -> None:
    """Two simulated requests with different Surface kinds: each cycle
    is fully contained. Pins the `bind -> clear -> bind -> clear`
    cadence the middleware uses across requests reusing the same
    asyncio task."""
    bind_surface_context(SYSTEM_HTTP_SURFACE_ID, SURFACE_KIND_HTTP)
    assert get_contextvars()["surface_kind"] == SURFACE_KIND_HTTP
    clear_surface_context()
    assert "surface_kind" not in get_contextvars()

    bind_surface_context(SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID, SURFACE_KIND_MCP_STREAMABLE_HTTP)
    assert get_contextvars()["surface_kind"] == SURFACE_KIND_MCP_STREAMABLE_HTTP
    clear_surface_context()
    assert "surface_kind" not in get_contextvars()
