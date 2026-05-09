"""Smoke tests for the Phase 1a port adapters."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.ports import (
    Allow,
    AllowAllAuthorize,
    FrozenClock,
    SystemClock,
    UUIDv7Generator,
)


@pytest.mark.unit
def test_system_clock_returns_utc() -> None:
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo == UTC


@pytest.mark.unit
def test_frozen_clock_returns_fixed_time() -> None:
    fixed = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
    clock = FrozenClock(fixed)
    assert clock.now() == fixed


@pytest.mark.unit
def test_uuidv7_generator_yields_unique_uuids() -> None:
    gen = UUIDv7Generator()
    ids = [gen.new_id() for _ in range(100)]
    assert len(set(ids)) == 100
    assert all(isinstance(i, UUID) for i in ids)


@pytest.mark.unit
def test_uuidv7_generator_yields_time_ordered_uuids() -> None:
    """UUIDv7 ids generated in sequence should sort in generation order."""
    gen = UUIDv7Generator()
    ids = [gen.new_id() for _ in range(50)]
    assert ids == sorted(ids)


@pytest.mark.unit
async def test_allow_all_authorize_returns_allow() -> None:
    authz = AllowAllAuthorize()
    result = await authz(
        principal_id=UUID("00000000-0000-0000-0000-000000000000"),
        command_name="RegisterActor",
        conduit="default",
    )
    assert isinstance(result, Allow)
