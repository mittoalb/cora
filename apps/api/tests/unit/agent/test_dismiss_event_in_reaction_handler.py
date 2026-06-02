"""Unit tests for the `dismiss_event_in_reaction` handler.

The handler is mostly SQL plumbing; the unit layer pins the two
shapes that don't need a real Postgres:

  - Authz deny short-circuits BEFORE any pool acquisition.
  - In-memory mode (pool is None) raises DismissalRequiresPostgresError
    BEFORE any decider call.

Everything else (bookmark NotFound, event NotFound, happy-path atomic
write) is covered in the integration test against real PG, where the
SQL semantics actually matter.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from cora.agent.errors import (
    DismissalRequiresPostgresError,
    UnauthorizedError,
)
from cora.agent.features.dismiss_event_in_reaction import (
    DismissEventInReaction,
    bind,
)
from cora.infrastructure.ports.authorize import Allow, Deny

_NOW = datetime(2026, 6, 2, 14, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000007007")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c1d0")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee01")


def _stub_kernel(*, pool: object | None, authz_allows: bool) -> MagicMock:
    """Build a minimal Kernel-shaped MagicMock for the two early
    branches we exercise here. The full Kernel is heavy; the handler
    only touches authz + pool + clock + id_generator before raising
    on those early branches, so a duck-typed MagicMock without
    `spec=` is enough."""
    kernel = MagicMock()
    kernel.pool = pool
    kernel.clock.now = MagicMock(return_value=_NOW)
    kernel.id_generator.new_id = MagicMock(
        return_value=UUID("01900000-0000-7000-8000-0000000d1551"),
    )
    if authz_allows:
        kernel.authz.authorize = AsyncMock(return_value=Allow())
    else:
        kernel.authz.authorize = AsyncMock(return_value=Deny(reason="denied by policy"))
    return kernel


def _command() -> DismissEventInReaction:
    return DismissEventInReaction(
        subscriber_name="run_debriefer",
        event_id=_EVENT_ID,
        reason="stuck on schema rename",
    )


@pytest.mark.asyncio
async def test_authz_deny_raises_unauthorized_without_touching_pool() -> None:
    """Authz runs first; a Deny verdict short-circuits with
    UnauthorizedError BEFORE any pool acquisition. Pin so a future
    refactor that reorders authz after pool acquisition would
    leak pool connections on every denied call."""
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=AssertionError("pool must not be touched"))
    kernel = _stub_kernel(pool=pool, authz_allows=False)

    handler = bind(kernel)

    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert not pool.acquire.called


@pytest.mark.asyncio
async def test_in_memory_mode_raises_dismissal_requires_postgres() -> None:
    """`deps.pool is None` (in-memory test config / dev without PG):
    the slice cannot advance projection_bookmarks because the table
    does not exist. Raise loudly instead of silently writing a
    Decision-only no-op."""
    kernel = _stub_kernel(pool=None, authz_allows=True)
    handler = bind(kernel)

    with pytest.raises(DismissalRequiresPostgresError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
