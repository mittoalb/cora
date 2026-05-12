"""Unit tests for `drain_projections` shape against an empty registry.

Behavior with a real registry + projections is integration-test
territory (needs a Postgres pool to read bookmarks + head position).
This file only pins the empty-registry no-op + the timeout exception
shape. Real drain behavior is covered in
`tests/integration/test_projection_worker_postgres.py` (8e-1b).
"""

import pytest

from cora.infrastructure.projection import (
    ProjectionDrainTimeoutError,
    ProjectionRegistry,
    drain_projections,
)


@pytest.mark.unit
async def test_drain_empty_registry_is_no_op() -> None:
    """No projections means nothing to drain; helper returns
    immediately without touching the pool. Pin this so a future
    refactor doesn't accidentally require a non-None pool."""
    registry = ProjectionRegistry()
    # Pool is not consulted when the registry is empty; pass None
    # to prove no method is called on it.
    await drain_projections(None, registry, deadline_seconds=0.5)  # type: ignore[arg-type]


@pytest.mark.unit
def test_drain_timeout_carries_diagnostic_state() -> None:
    """The exception body should make it obvious WHY the drain
    failed (per-projection subscribed head vs. each bookmark) so a
    flaky integration test surfaces the lag at a glance.

    The drain compares each projection's bookmark to ITS subscribed
    head (max position of an event with one of its subscribed types),
    not the global head, so multi-projection BCs don't trip the
    timeout when one projection is genuinely idle.
    """
    exc = ProjectionDrainTimeoutError(
        deadline_seconds=2.5,
        subscribed_heads={"proj_a": 42, "proj_b": 41},
        bookmarks={"proj_a": 40, "proj_b": 41},
    )
    msg = str(exc)
    assert "2.5" in msg
    assert "42" in msg
    assert "proj_a" in msg
    assert "proj_b" in msg
    assert exc.subscribed_heads["proj_a"] == 42
    assert exc.bookmarks["proj_a"] == 40
