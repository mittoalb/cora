"""Integration tests for `PostgresEventStore.append_streams` against a real Postgres.

Pins the cross-stream atomic write contract under the real adapter:
all-or-nothing, per-stream version checks, single Postgres
transaction (so all events get the same `xid8`), event_id UNIQUE
constraint spans the entire batch.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
    StreamAppend,
)


def _event(
    *,
    event_id: UUID | None = None,
    event_type: str = "Recorded",
) -> NewEvent:
    return NewEvent(
        event_id=event_id if event_id is not None else uuid4(),
        event_type=event_type,
        schema_version=1,
        payload={"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=uuid4(),
    )


@pytest.mark.integration
async def test_append_streams_writes_to_two_streams_atomically(db_pool: asyncpg.Pool) -> None:
    store = PostgresEventStore(db_pool)
    parent_id, child_id = uuid4(), uuid4()

    versions = await store.append_streams(
        [
            StreamAppend(
                "AppendStreamsTestParent", parent_id, expected_version=0, events=[_event()]
            ),
            StreamAppend(
                "AppendStreamsTestChild", child_id, expected_version=0, events=[_event(), _event()]
            ),
        ]
    )
    assert versions == {parent_id: 1, child_id: 2}

    parent_events, _ = await store.load("AppendStreamsTestParent", parent_id)
    child_events, _ = await store.load("AppendStreamsTestChild", child_id)
    assert len(parent_events) == 1
    assert len(child_events) == 2


@pytest.mark.integration
async def test_append_streams_shares_transaction_id_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """All events in one append_streams call land in the same Postgres
    transaction, so they MUST share `xid8` -- the projection-cursor's
    correctness depends on it (per the event_store module docstring)."""
    store = PostgresEventStore(db_pool)
    parent_id, child_id = uuid4(), uuid4()

    await store.append_streams(
        [
            StreamAppend("TxIdTestParent", parent_id, expected_version=0, events=[_event()]),
            StreamAppend("TxIdTestChild", child_id, expected_version=0, events=[_event()]),
        ]
    )
    parent_events, _ = await store.load("TxIdTestParent", parent_id)
    child_events, _ = await store.load("TxIdTestChild", child_id)
    assert parent_events[0].transaction_id == child_events[0].transaction_id


@pytest.mark.integration
async def test_append_streams_rolls_back_on_concurrency_mismatch(db_pool: asyncpg.Pool) -> None:
    """A version conflict on the SECOND stream aborts the entire batch.
    The first stream's append is rolled back even though its own
    expected_version was correct.

    The conflict mechanism: the second stream already has events at the
    versions we're trying to insert -- the UNIQUE (stream_type,
    stream_id, version) constraint fires, mapped to `ConcurrencyError`.
    Both seeded streams stay at their pre-batch state.
    """
    store = PostgresEventStore(db_pool)
    parent_id, child_id = uuid4(), uuid4()
    # Seed parent (version 1) and child (version 1) so we can trip the
    # child's UNIQUE constraint by attempting expected_version=0.
    await store.append("RollbackTestParent", parent_id, expected_version=0, events=[_event()])
    await store.append("RollbackTestChild", child_id, expected_version=0, events=[_event()])

    with pytest.raises(ConcurrencyError) as exc_info:
        await store.append_streams(
            [
                # Parent expects 1 (matches reality) -- would succeed alone
                StreamAppend(
                    "RollbackTestParent", parent_id, expected_version=1, events=[_event()]
                ),
                # Child claims expected_version=0 -- collides with the seeded
                # version 1 row, forcing the whole batch to roll back.
                StreamAppend("RollbackTestChild", child_id, expected_version=0, events=[_event()]),
            ]
        )
    assert exc_info.value.stream_id == child_id
    assert exc_info.value.expected == 0
    assert exc_info.value.actual == 1

    # Parent stayed at version 1 (the rolled-back batch never landed)
    parent_events, parent_v = await store.load("RollbackTestParent", parent_id)
    assert parent_v == 1
    assert len(parent_events) == 1
    # Child also stayed at version 1
    child_events, child_v = await store.load("RollbackTestChild", child_id)
    assert child_v == 1
    assert len(child_events) == 1


@pytest.mark.integration
async def test_append_streams_rolls_back_when_first_stream_version_mismatches(
    db_pool: asyncpg.Pool,
) -> None:
    """Atomicity is order-independent. The sibling
    `rolls_back_on_concurrency_mismatch` test puts the offending stream
    second; this pins the symmetric case where the FIRST stream's
    `expected_version` is wrong. The trailing stream's append would
    succeed on its own but must not materialize."""
    store = PostgresEventStore(db_pool)
    parent_id, child_id = uuid4(), uuid4()
    # Seed parent at version 1 so its expected_version=0 collides.
    await store.append("OrderIndepTestParent", parent_id, expected_version=0, events=[_event()])

    with pytest.raises(ConcurrencyError) as exc_info:
        await store.append_streams(
            [
                # Parent claims expected_version=0 -- collides with the seeded
                # version-1 row, must roll the whole batch back.
                StreamAppend(
                    "OrderIndepTestParent", parent_id, expected_version=0, events=[_event()]
                ),
                # Child is fresh; expected_version=0 is correct and would
                # succeed alone -- but atomicity must keep it from landing.
                StreamAppend(
                    "OrderIndepTestChild", child_id, expected_version=0, events=[_event()]
                ),
            ]
        )
    assert exc_info.value.stream_id == parent_id
    assert exc_info.value.expected == 0
    assert exc_info.value.actual == 1

    # Parent stayed at version 1; child never materialized.
    _, parent_v = await store.load("OrderIndepTestParent", parent_id)
    assert parent_v == 1
    _, child_v = await store.load("OrderIndepTestChild", child_id)
    assert child_v == 0


@pytest.mark.integration
async def test_append_streams_rolls_back_on_duplicate_event_id_within_batch(
    db_pool: asyncpg.Pool,
) -> None:
    """The `events_event_id_unique` constraint spans the entire batch.
    If two StreamAppends share an event_id, the second insert trips the
    constraint and the whole transaction rolls back -- neither stream
    materializes. The PG adapter only maps the stream-version UNIQUE
    constraint to `ConcurrencyError`; any other UNIQUE violation
    surfaces unchanged. This is the silent failure mode that would
    mask cross-aggregate writes (amend_clearance,
    promote_caution_proposal) if the batch ever fell back to per-stream
    transactions."""
    store = PostgresEventStore(db_pool)
    parent_id, child_id = uuid4(), uuid4()
    shared = uuid4()

    with pytest.raises(asyncpg.UniqueViolationError):
        await store.append_streams(
            [
                StreamAppend(
                    "DupEventIdTestParent",
                    parent_id,
                    expected_version=0,
                    events=[_event(event_id=shared)],
                ),
                StreamAppend(
                    "DupEventIdTestChild",
                    child_id,
                    expected_version=0,
                    events=[_event(event_id=shared)],
                ),
            ]
        )

    # Neither stream landed (whole-batch rollback).
    _, parent_v = await store.load("DupEventIdTestParent", parent_id)
    _, child_v = await store.load("DupEventIdTestChild", child_id)
    assert parent_v == 0
    assert child_v == 0


@pytest.mark.integration
async def test_append_single_stream_delegates_through_append_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """`append` is now a wrapper around `append_streams`. Round-trip
    behavior should be byte-identical to the multi-stream path."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    new_version = await store.append(
        "AppendDelegateTest", stream_id, expected_version=0, events=[_event(), _event()]
    )
    assert new_version == 2
    events, version = await store.load("AppendDelegateTest", stream_id)
    assert version == 2
    assert len(events) == 2


@pytest.mark.integration
async def test_event_id_collision_across_separate_transactions_rejected_globally(
    db_pool: asyncpg.Pool,
) -> None:
    """`events_event_id_unique` is a GLOBAL INDEX, not a per-batch or
    per-stream check: a duplicate event_id arriving in a SECOND
    transaction (after the first has already committed) MUST also be
    rejected. This catches a hypothetical regression where a future
    change scoped the constraint to a partition or per-stream
    namespace.

    The cross-aggregate atomic-write slices (`define_agent`,
    `amend_clearance`, `promote_caution_proposal`,
    `add_run_to_campaign`) rely on the global namespace to be
    confident an event_id retried from a buggy idempotency-cache
    will surface loudly as a `UniqueViolationError` instead of
    silently overwriting or co-existing with the original."""
    store = PostgresEventStore(db_pool)
    first_stream_id, second_stream_id = uuid4(), uuid4()
    shared = uuid4()

    await store.append_streams(
        [
            StreamAppend(
                "CrossTxCollisionFirst",
                first_stream_id,
                expected_version=0,
                events=[_event(event_id=shared)],
            ),
        ]
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await store.append_streams(
            [
                StreamAppend(
                    "CrossTxCollisionSecond",
                    second_stream_id,
                    expected_version=0,
                    events=[_event(event_id=shared)],
                ),
            ]
        )

    _, first_v = await store.load("CrossTxCollisionFirst", first_stream_id)
    _, second_v = await store.load("CrossTxCollisionSecond", second_stream_id)
    assert first_v == 1
    assert second_v == 0


@pytest.mark.integration
async def test_event_id_collision_across_different_stream_types_rejected_globally(
    db_pool: asyncpg.Pool,
) -> None:
    """The global UNIQUE INDEX MUST reject a collision even when the
    two events belong to entirely different aggregate stream-types
    (the cross-BC case: an Agent stream and a Caution stream cannot
    both carry the same event_id). Without this property, two
    independently-written aggregates could share an event_id and
    `causation_id`-based reconstruction would become ambiguous."""
    store = PostgresEventStore(db_pool)
    agent_stream_id, caution_stream_id = uuid4(), uuid4()
    shared = uuid4()

    await store.append_streams(
        [
            StreamAppend(
                "AgentLikeStream",
                agent_stream_id,
                expected_version=0,
                events=[_event(event_id=shared, event_type="AgentDefined")],
            ),
        ]
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await store.append_streams(
            [
                StreamAppend(
                    "CautionLikeStream",
                    caution_stream_id,
                    expected_version=0,
                    events=[_event(event_id=shared, event_type="CautionRegistered")],
                ),
            ]
        )


@pytest.mark.integration
async def test_event_id_collision_failure_does_not_block_subsequent_retry_with_fresh_id(
    db_pool: asyncpg.Pool,
) -> None:
    """After a `UniqueViolationError`, the rejected stream is intact
    (version 0). Re-issuing the same write with a fresh event_id MUST
    succeed -- the constraint failure leaves no residual state and the
    pool is healthy after the rollback. Locks the recovery path so a
    transient collision doesn't poison the stream."""
    store = PostgresEventStore(db_pool)
    other_stream_id, retry_stream_id = uuid4(), uuid4()
    shared = uuid4()

    await store.append_streams(
        [
            StreamAppend(
                "OtherStream",
                other_stream_id,
                expected_version=0,
                events=[_event(event_id=shared)],
            ),
        ]
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await store.append_streams(
            [
                StreamAppend(
                    "RetryStream",
                    retry_stream_id,
                    expected_version=0,
                    events=[_event(event_id=shared)],
                ),
            ]
        )

    new_versions = await store.append_streams(
        [
            StreamAppend(
                "RetryStream",
                retry_stream_id,
                expected_version=0,
                events=[_event(event_id=uuid4())],
            ),
        ]
    )
    assert new_versions == {retry_stream_id: 1}
