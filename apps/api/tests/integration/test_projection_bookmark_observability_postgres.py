"""Projection observability day-1 hook integration tests.

Pins the 4 new columns on `projection_bookmarks` round-trip
correctly through the worker's success path AND the new
`write_bookmark_failure` helper:

  - `last_event_recorded_at` advances with each successful batch
  - `last_error_at` / `last_error_message` populate on failure,
    clear on next success
  - `consecutive_failures` increments on failure, resets to 0 on
    success
  - Failure path does NOT touch the bookmark position
  - Long error messages truncate to 500 chars

Pre-positions for the full read-side observability surface (admin
endpoint + lag sampler + OTel) which stays deferred until the
trigger fires (see project_deferred.md).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.ports.event_store import NewEvent, StoredEvent
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.projection.bookmark import (
    write_bookmark_failure,
)
from cora.infrastructure.projection.handler import ConnectionLike
from cora.infrastructure.projection.worker import advance_subscriber_once


class _CapturingProjection:
    """Test-only projection: captures events, no side effects."""

    name = "proj_test_phase_8e_9_observability"
    subscribed_event_types = frozenset({"Phase8e9Event"})

    def __init__(self) -> None:
        self.captured: list[StoredEvent] = []

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        _ = conn
        self.captured.append(event)


async def _ensure_bookmark(db_pool: asyncpg.Pool, name: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO projection_bookmarks (name) VALUES ($1) ON CONFLICT DO NOTHING",
            name,
        )


async def _read_bookmark_columns(db_pool: asyncpg.Pool, name: str) -> dict[str, object]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                last_transaction_id::text AS last_transaction_id,
                last_position,
                last_event_recorded_at,
                last_error_at,
                last_error_message,
                consecutive_failures
            FROM projection_bookmarks
            WHERE name = $1
            """,
            name,
        )
    assert row is not None
    return dict(row)


def _make_event(principal: UUID, payload: dict[str, object] | None = None) -> NewEvent:
    return NewEvent(
        event_id=uuid4(),
        event_type="Phase8e9Event",
        schema_version=1,
        payload=payload or {"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=principal,
    )


@pytest.mark.integration
async def test_successful_drain_populates_observability_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """The load-bearing success-path test: after a successful batch
    advance, every new column has the right value."""
    projection = _CapturingProjection()
    await _ensure_bookmark(db_pool, projection.name)

    store = PostgresEventStore(db_pool)
    principal = UUID("01900000-0000-7000-8000-00000000ee01")
    await store.append(
        "TestStream",
        uuid4(),
        0,
        [_make_event(principal)],
    )

    processed = await advance_subscriber_once(db_pool, projection, batch_size=10)
    assert processed == 1

    cols = await _read_bookmark_columns(db_pool, projection.name)
    assert cols["last_event_recorded_at"] is not None, (
        "last_event_recorded_at should be set to the applied event's recorded_at"
    )
    assert cols["last_error_at"] is None
    assert cols["last_error_message"] is None
    assert cols["consecutive_failures"] == 0
    # Sanity: position advanced past the sentinel
    assert int(cols["last_transaction_id"]) > 0  # type: ignore[arg-type]
    assert cols["last_position"] > 0  # type: ignore[operator]


@pytest.mark.integration
async def test_failure_helper_records_error_and_increments_counter(
    db_pool: asyncpg.Pool,
) -> None:
    """write_bookmark_failure populates last_error_at, last_error_message,
    and increments consecutive_failures."""
    projection_name = "proj_test_phase_8e_9_failure_basic"
    await _ensure_bookmark(db_pool, projection_name)

    await write_bookmark_failure(
        db_pool,
        projection_name,
        error_message="boom: something went wrong",
    )

    cols = await _read_bookmark_columns(db_pool, projection_name)
    assert cols["last_error_at"] is not None
    assert cols["last_error_message"] == "boom: something went wrong"
    assert cols["consecutive_failures"] == 1


@pytest.mark.integration
async def test_failure_helper_does_not_touch_position(
    db_pool: asyncpg.Pool,
) -> None:
    """Failure path preserves bookmark position so retry semantics
    are intact. Set position to a known value, fire failure, assert
    position unchanged."""
    projection_name = "proj_test_phase_8e_9_position_preserved"
    await _ensure_bookmark(db_pool, projection_name)

    # Set position to a non-sentinel value
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE projection_bookmarks
            SET last_transaction_id = '42'::xid8, last_position = 7
            WHERE name = $1
            """,
            projection_name,
        )

    await write_bookmark_failure(
        db_pool,
        projection_name,
        error_message="failed",
    )

    cols = await _read_bookmark_columns(db_pool, projection_name)
    assert cols["last_transaction_id"] == "42"
    assert cols["last_position"] == 7
    assert cols["consecutive_failures"] == 1


@pytest.mark.integration
async def test_consecutive_failures_increment_across_calls(
    db_pool: asyncpg.Pool,
) -> None:
    """Three consecutive failures land consecutive_failures = 3 with
    the latest error message."""
    projection_name = "proj_test_phase_8e_9_consecutive_increment"
    await _ensure_bookmark(db_pool, projection_name)

    for i in range(3):
        await write_bookmark_failure(
            db_pool,
            projection_name,
            error_message=f"failure number {i}",
        )

    cols = await _read_bookmark_columns(db_pool, projection_name)
    assert cols["consecutive_failures"] == 3
    assert cols["last_error_message"] == "failure number 2"


@pytest.mark.integration
async def test_success_after_failure_clears_failure_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """The recovery path: failure recorded → next successful drain
    clears the error columns and resets counter to 0."""
    projection = _CapturingProjection()
    # Use a unique name to avoid collision with the success-path test.
    # `_CapturingProjection` is a regular class (not a frozen dataclass),
    # so plain attribute assignment shadows the class-level default.
    projection.name = "proj_test_phase_8e_9_recovery"
    await _ensure_bookmark(db_pool, projection.name)

    # First, record some failures
    for i in range(2):
        await write_bookmark_failure(
            db_pool,
            projection.name,
            error_message=f"prior failure {i}",
        )
    cols_before = await _read_bookmark_columns(db_pool, projection.name)
    assert cols_before["consecutive_failures"] == 2
    assert cols_before["last_error_message"] == "prior failure 1"
    assert cols_before["last_event_recorded_at"] is None, (
        "no successful batch yet, so last_event_recorded_at should still be NULL"
    )

    # Now successful drain
    store = PostgresEventStore(db_pool)
    principal = UUID("01900000-0000-7000-8000-00000000ee02")
    await store.append("TestStream", uuid4(), 0, [_make_event(principal)])
    processed = await advance_subscriber_once(db_pool, projection, batch_size=10)
    assert processed == 1

    cols_after = await _read_bookmark_columns(db_pool, projection.name)
    assert cols_after["last_error_at"] is None, "error timestamp should clear on success"
    assert cols_after["last_error_message"] is None, "error message should clear on success"
    assert cols_after["consecutive_failures"] == 0, "counter should reset to 0 on success"
    assert isinstance(cols_after["last_event_recorded_at"], datetime), (
        "last_event_recorded_at should advance from NULL to the applied event's recorded_at"
    )


@pytest.mark.integration
async def test_long_error_message_truncated_at_500_chars(
    db_pool: asyncpg.Pool,
) -> None:
    """Bound bookmark UPDATE size: long error messages truncate to
    500 chars at the helper layer (full traceback goes to OTel
    spans when full surface ships)."""
    projection_name = "proj_test_phase_8e_9_truncation"
    await _ensure_bookmark(db_pool, projection_name)

    long_message = "x" * 1000
    await write_bookmark_failure(
        db_pool,
        projection_name,
        error_message=long_message,
    )

    cols = await _read_bookmark_columns(db_pool, projection_name)
    stored = cols["last_error_message"]
    assert isinstance(stored, str)
    assert len(stored) == 500
    assert stored == "x" * 500
