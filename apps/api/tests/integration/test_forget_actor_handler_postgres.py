"""End-to-end integration test: forget_actor handler against real Postgres.

Pins the single-transaction atomicity contract: the
`actor_profile` row scrub+delete AND the `ActorProfileForgotten`
event append commit in ONE Postgres transaction so a failure on
either half rolls both back. Verified by:

  1. Happy path: register an actor, forget the actor, assert the
     actor_profile row is gone AND the event landed on the stream.
  2. Atomic rollback: drive scrub+delete + a stale-version append
     through the same conn.transaction() block; confirm the
     ConcurrencyError on append rolls back the scrub, leaving the
     actor_profile row intact under MVCC.
  3. Unknown actor: ActorNotFoundError surfaces before any I/O.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.aggregates.actor import ActorNotFoundError
from cora.access.features import forget_actor, register_actor
from cora.access.features.forget_actor import ForgetActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import ConcurrencyError, StreamAppend
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_handler_scrubs_profile_and_appends_audit_event(
    db_pool: asyncpg.Pool,
) -> None:
    actor_id = uuid4()
    register_event_id = uuid4()
    forget_event_id = uuid4()
    profile_store = make_pg_profile_store(db_pool)
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[actor_id, register_event_id, forget_event_id],
        profile_store=profile_store,
    )

    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert (await profile_store.get(actor_id)) is not None

    handler = forget_actor.bind(deps)
    await handler(
        ForgetActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Vault row gone.
    assert (await profile_store.get(actor_id)) is None

    # Event landed on the stream.
    events, version = await deps.event_store.load("Actor", actor_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "ActorRegisteredV2",
        "ActorProfileForgotten",
    ]
    forgotten = events[1]
    assert forgotten.payload == {
        "actor_id": str(actor_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.integration
async def test_scrub_rolls_back_when_event_append_conflicts_in_same_transaction(
    db_pool: asyncpg.Pool,
) -> None:
    """Single-transaction contract: when the in-transaction
    append_streams raises ConcurrencyError, the scrub_and_delete
    rolls back via MVCC and the actor_profile row remains intact.
    Exercises EventStore.append_streams(conn=...) directly so the
    failure is fully deterministic without racing the handler."""
    actor_id = uuid4()
    profile_store = make_pg_profile_store(db_pool)
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[actor_id, uuid4()],
        profile_store=profile_store,
    )

    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert (await profile_store.get(actor_id)) is not None

    dummy_event = to_new_event(
        event_type="ActorDeactivated",
        payload={
            "actor_id": str(actor_id),
            "occurred_at": _NOW.isoformat(),
        },
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="ForcedConflictForRollbackTest",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    bad_append = StreamAppend(
        stream_type="Actor",
        stream_id=actor_id,
        expected_version=0,  # stale: stream is already at version 1
        events=[dummy_event],
    )

    # Mirror the handler's transaction block: scrub first, then
    # append. The bad expected_version raises ConcurrencyError;
    # leaving the with-block rolls back the scrub.
    with pytest.raises(ConcurrencyError):
        async with db_pool.acquire() as conn, conn.transaction():
            await profile_store.scrub_and_delete(conn, actor_id)
            await deps.event_store.append_streams([bad_append], conn=conn)

    # MVCC restored the row: vault still populated AFTER the
    # rolled-back transaction.
    profile = await profile_store.get(actor_id)
    assert profile is not None
    assert profile.name == "Doga"


@pytest.mark.integration
async def test_handler_raises_actor_not_found_for_unknown_id(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    handler = forget_actor.bind(deps)
    unknown = uuid4()

    with pytest.raises(ActorNotFoundError) as exc_info:
        await handler(
            ForgetActor(actor_id=unknown),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.actor_id == unknown
