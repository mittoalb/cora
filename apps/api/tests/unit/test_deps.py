"""Unit tests for the `build_shared_deps` wiring.

Verifies the `app_env` branching: `test` selects the in-memory store and
a no-op teardown; the production branch is exercised by integration tests
that have a real Postgres available.
"""

import pytest

from cora.infrastructure.deps import build_shared_deps
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore


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
