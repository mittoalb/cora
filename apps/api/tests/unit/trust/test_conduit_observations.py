"""Unit tests for the ConduitTraversal observation dataclass + adapters.

The Postgres adapter's SQL is exercised by the integration test
(`test_trust_authorize_traversals_postgres.py`). This file covers
the InMemory adapter's contract behaviors:
  - append accepts an empty list (no-op)
  - append stores rows by event_id
  - retry with the same event_id is a no-op (mirrors Postgres's
    ON CONFLICT (event_id) DO NOTHING)
  - all returns rows in insertion order (test convenience)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.conduit.observations import (
    ConduitTraversal,
    InMemoryTraversalStore,
)

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _traversal(*, event_id: object | None = None) -> ConduitTraversal:
    return ConduitTraversal(
        event_id=event_id or uuid4(),  # type: ignore[arg-type]
        conduit_id=uuid4(),
        channel_id=uuid4(),
        actor_id=uuid4(),
        command_name="StartRun",
        decision="Allow",
        reason=None,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
async def test_in_memory_append_empty_list_is_noop() -> None:
    store = InMemoryTraversalStore()
    await store.append([])
    assert store.all() == []


@pytest.mark.unit
async def test_in_memory_append_persists_rows_by_event_id() -> None:
    store = InMemoryTraversalStore()
    row_a = _traversal()
    row_b = _traversal()
    await store.append([row_a, row_b])
    persisted = store.all()
    assert len(persisted) == 2
    assert {r.event_id for r in persisted} == {row_a.event_id, row_b.event_id}


@pytest.mark.unit
async def test_in_memory_append_with_duplicate_event_id_is_noop() -> None:
    """Idempotency guarantee: producer retries are safe.

    Mirrors the Postgres adapter's `ON CONFLICT (event_id) DO NOTHING`
    semantics. The first write wins; later writes with the same
    event_id are silently dropped.
    """
    store = InMemoryTraversalStore()
    event_id = uuid4()
    first = ConduitTraversal(
        event_id=event_id,
        conduit_id=uuid4(),
        channel_id=uuid4(),
        actor_id=uuid4(),
        command_name="StartRun",
        decision="Allow",
        reason=None,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
    )
    # Different content but same event_id.
    second = ConduitTraversal(
        event_id=event_id,
        conduit_id=uuid4(),
        channel_id=uuid4(),
        actor_id=uuid4(),
        command_name="DefinePolicy",
        decision="Deny",
        reason="other",
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
    )
    await store.append([first])
    await store.append([second])

    persisted = store.all()
    assert len(persisted) == 1
    # First write wins.
    assert persisted[0].command_name == "StartRun"
    assert persisted[0].decision == "Allow"


@pytest.mark.unit
async def test_in_memory_append_supports_batched_writes() -> None:
    """G4 lock: the API takes a list, batched writes work in one call."""
    store = InMemoryTraversalStore()
    rows = [_traversal() for _ in range(5)]
    await store.append(rows)
    assert len(store.all()) == 5
