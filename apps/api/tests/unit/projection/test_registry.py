"""Unit tests for ProjectionRegistry."""

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection import (
    DuplicateProjectionError,
    ProjectionRegistry,
)
from cora.infrastructure.projection.handler import ConnectionLike


class _NoopProjection:
    """Minimal Projection-shaped object for testing the registry.

    Uses instance attrs (not ClassVar) so each test can construct
    distinct projections inline. Python's structural typing accepts
    this for the Projection Protocol because the Protocol's ClassVar
    declarations document intent without enforcing the storage
    location.
    """

    def __init__(self, name: str, types: frozenset[str]) -> None:
        self.name = name
        self.subscribed_event_types = types

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        return None


@pytest.mark.unit
def test_empty_registry_is_empty() -> None:
    registry = ProjectionRegistry()
    assert registry.is_empty()
    assert len(registry) == 0
    assert registry.names() == frozenset()


@pytest.mark.unit
def test_register_one_projection() -> None:
    registry = ProjectionRegistry()
    registry.register(_NoopProjection("proj_test", frozenset({"X"})))

    assert not registry.is_empty()
    assert len(registry) == 1
    assert registry.names() == frozenset({"proj_test"})
    assert registry.get("proj_test") is not None
    assert registry.get("nonexistent") is None


@pytest.mark.unit
def test_register_iterates_in_insertion_order() -> None:
    registry = ProjectionRegistry()
    registry.register(_NoopProjection("a", frozenset({"X"})))
    registry.register(_NoopProjection("b", frozenset({"Y"})))
    registry.register(_NoopProjection("c", frozenset({"Z"})))

    assert [p.name for p in registry] == ["a", "b", "c"]


@pytest.mark.unit
def test_duplicate_name_raises() -> None:
    """Names key the bookmark row + the proj_* table; collisions are
    silent corruption hazards."""
    registry = ProjectionRegistry()
    registry.register(_NoopProjection("proj_dup", frozenset({"X"})))
    with pytest.raises(DuplicateProjectionError, match="proj_dup"):
        registry.register(_NoopProjection("proj_dup", frozenset({"Y"})))
