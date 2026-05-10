"""Unit tests for the `build_shared_deps` wiring.

Verifies the `app_env` branching: `test` selects the in-memory store and
a no-op teardown; the production branch is exercised by integration tests
that have a real Postgres available.

Also covers the Authorize-adapter selection driven by
`Settings.trust_policy_id`: unset → AllowAllAuthorize; set →
TrustAuthorize.
"""

from uuid import UUID

import pytest

from cora.infrastructure.deps import build_shared_deps
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import AllowAllAuthorize
from cora.trust.authorize import TrustAuthorize


@pytest.mark.unit
async def test_build_shared_deps_uses_in_memory_stores_in_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")

    deps, teardown = await build_shared_deps()

    assert deps.settings.app_env == "test"
    assert isinstance(deps.event_store, InMemoryEventStore)
    assert isinstance(deps.idempotency_store, InMemoryIdempotencyStore)
    # Teardown is a no-op in test mode but must still be awaitable.
    await teardown()


@pytest.mark.unit
async def test_build_shared_deps_populates_all_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every BC's wiring relies on these fields being present and non-None."""
    monkeypatch.setenv("APP_ENV", "test")

    deps, teardown = await build_shared_deps()

    assert deps.clock is not None
    assert deps.id_generator is not None
    assert deps.authorize is not None
    assert deps.event_store is not None
    assert deps.idempotency_store is not None
    await teardown()


@pytest.mark.unit
async def test_build_shared_deps_uses_allow_all_authorize_when_no_policy_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 1 permissive default: no `trust_policy_id` → no real auth.
    Tests + dev environments rely on this; flipping it to fail-closed
    would be a significant behavior change."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)

    deps, teardown = await build_shared_deps()
    assert isinstance(deps.authorize, AllowAllAuthorize)
    await teardown()


@pytest.mark.unit
async def test_build_shared_deps_uses_trust_authorize_when_policy_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting `trust_policy_id` swaps to the real Trust adapter.
    The adapter loads the configured policy at request time; this test
    verifies the WIRING, not the gating semantics (those live in
    `tests/unit/trust/test_trust_authorize.py`)."""
    monkeypatch.setenv("APP_ENV", "test")
    policy_id = UUID("01900000-0000-7000-8000-000000000601")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    deps, teardown = await build_shared_deps()
    assert isinstance(deps.authorize, TrustAuthorize)
    await teardown()
