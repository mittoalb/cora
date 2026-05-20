"""Behavioural contract suite for the `EventStore` port.

Every concrete `EventStore` adapter must satisfy the same observable
behaviour: load semantics, append semantics, optimistic concurrency,
event-id uniqueness, and multi-stream atomicity. This suite parametrizes
the canonical assertions over each implementation so the in-memory
adapter and the Postgres adapter prove themselves against the SAME
spec — preventing the classic hexagonal-architecture bug where the
in-memory test double silently diverges from production behaviour.

Pattern: Meszaros's "Abstract Test" / "Testcase Superclass" (xUnit Test
Patterns, 2007). pytest's parametrized-fixture idiom is the canonical
Python expression. See [[project-testing-expansion-research]] Corpus 3
for the broader survey.

NEW adapters added to the EventStore Protocol MUST be added to the
`event_store` fixture's `params` below; an architecture fitness test
in a later iter will enforce that "every concrete EventStore subclass
appears in this suite" so drift becomes impossible. For now, the
discipline is manual.

Sits in the integration tier so the Postgres branch can use the
existing `db_pool` fixture (per-test fresh DB from the migrated
template). The in-memory branch ignores db_pool — pytest builds the
container once per session regardless, so the overhead is amortized
across all integration tests, not paid per parametrize-case.

Iter J.1 of the testing-expansion rollout.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    EventStore,
    NewEvent,
    StreamAppend,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore

pytestmark = pytest.mark.integration


def _make_event(
    *,
    event_id: UUID | None = None,
    event_type: str = "ContractEvent",
    payload: dict[str, object] | None = None,
) -> NewEvent:
    return NewEvent(
        event_id=event_id if event_id is not None else uuid4(),
        event_type=event_type,
        schema_version=1,
        payload=payload or {},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=uuid4(),
    )


@pytest_asyncio.fixture(params=["inmem", "postgres"], ids=["inmem", "postgres"])
async def event_store(request: pytest.FixtureRequest, db_pool: asyncpg.Pool) -> EventStore:
    """Yield each EventStore impl in turn so contract assertions run twice."""
    if request.param == "inmem":
        return InMemoryEventStore()
    return PostgresEventStore(db_pool)


async def test_load_returns_empty_for_unknown_stream(event_store: EventStore) -> None:
    """Missing stream → `([], 0)`, NOT an error."""
    events, version = await event_store.load("ContractStream", uuid4())
    assert events == []
    assert version == 0


async def test_append_then_load_round_trips(event_store: EventStore) -> None:
    """Append N events; load returns the same N with monotonic versions 1..N."""
    stream_id = uuid4()
    new_events = [_make_event(payload={"step": i}) for i in range(3)]
    new_version = await event_store.append("ContractStream", stream_id, 0, new_events)
    assert new_version == 3
    loaded, version = await event_store.load("ContractStream", stream_id)
    assert version == 3
    assert [e.version for e in loaded] == [1, 2, 3]
    assert [e.event_id for e in loaded] == [e.event_id for e in new_events]


async def test_concurrency_error_on_stale_expected_version(
    event_store: EventStore,
) -> None:
    """Second append with stale expected_version raises ConcurrencyError."""
    stream_id = uuid4()
    await event_store.append("ContractStream", stream_id, 0, [_make_event()])
    with pytest.raises(ConcurrencyError) as exc:
        await event_store.append("ContractStream", stream_id, 0, [_make_event()])
    assert exc.value.expected == 0
    assert exc.value.actual == 1


async def test_event_id_must_be_unique_within_a_batch(event_store: EventStore) -> None:
    """Two events with the same event_id in one append → both adapters reject.

    In-memory raises `ValueError`; Postgres raises `UniqueViolationError`
    (a subclass of `Exception`). The contract is "rejects" — both impls
    fail loud, which is what matters for downstream dedup correctness.
    """
    shared = uuid4()
    with pytest.raises(Exception):  # noqa: B017  (deliberate cross-impl)
        await event_store.append(
            "ContractStream",
            uuid4(),
            0,
            [_make_event(event_id=shared), _make_event(event_id=shared)],
        )


async def test_event_id_must_be_unique_across_appends(event_store: EventStore) -> None:
    """An event_id used in one stream cannot reappear in a later append.

    The dedup key for downstream projection consumers is `event_id`;
    duplicates would break at-least-once delivery's idempotency guarantees.
    """
    shared = uuid4()
    await event_store.append("ContractStream", uuid4(), 0, [_make_event(event_id=shared)])
    with pytest.raises(Exception):  # noqa: B017
        await event_store.append("ContractStream", uuid4(), 0, [_make_event(event_id=shared)])


async def test_append_streams_is_atomic_on_concurrency_failure(
    event_store: EventStore,
) -> None:
    """If ANY stream's expected_version mismatches, the WHOLE batch rolls
    back: no events from any stream become visible. This is the load-
    bearing invariant for cross-aggregate atomic writes (Safety BC's
    `amend_clearance`, Agent BC's `define_agent`).
    """
    stream_a = uuid4()
    stream_b = uuid4()
    # Pre-populate A with 1 event so its current version is 1.
    await event_store.append("ContractStream", stream_a, 0, [_make_event()])

    # Try a 2-stream batch where A's expected=0 is stale (current=1).
    # The batch must reject in its entirety; B's events must NOT persist.
    with pytest.raises(ConcurrencyError):
        await event_store.append_streams(
            [
                StreamAppend("ContractStream", stream_a, 0, [_make_event()]),
                StreamAppend("ContractStream", stream_b, 0, [_make_event()]),
            ]
        )

    events_b, version_b = await event_store.load("ContractStream", stream_b)
    assert events_b == []
    assert version_b == 0


async def test_append_streams_returns_version_map(event_store: EventStore) -> None:
    """`append_streams` returns `{stream_id: new_version}` for every input."""
    stream_a = uuid4()
    stream_b = uuid4()
    result = await event_store.append_streams(
        [
            StreamAppend("ContractStream", stream_a, 0, [_make_event(), _make_event()]),
            StreamAppend("ContractStream", stream_b, 0, [_make_event()]),
        ]
    )
    assert result == {stream_a: 2, stream_b: 1}
