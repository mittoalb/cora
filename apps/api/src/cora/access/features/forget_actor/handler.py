"""Application handler for the `forget_actor` PII-erasure slice.

Update-style handler shape with one wrinkle: the profile vault
scrub + delete AND the `ActorProfileForgotten` event append commit
in ONE Postgres transaction. Procedure:

    1. authorize(principal_id, command_name, conduit) -> Allow | Deny
    2. clock.now() -> domain timestamp
    3. event_store.load(stream_type, command.actor_id)
       -> (stored_events, current_version)
    4. fold([from_stored(s) for s in stored_events]) -> state
    5. decide(state, command, *, now) -> [ActorProfileForgotten]
    6. wrap event as NewEvent (via aggregate's to_payload)
    7. acquire pool conn + open transaction; INSIDE:
         a. profile_store.scrub_and_delete(conn, actor_id)
            (UPDATE name='' THEN DELETE so dead-tuple bytes
             carry no PII before VACUUM)
         b. event_store.append_streams([...], conn=conn)
    8. transaction commits both halves atomically

The two-phase write is wrapped by the `EventStore.append_streams`
port's optional `conn` kwarg (None for every other slice; the
PostgresEventStore reads from the caller's connection without
opening a nested transaction). In `app_env=test` (no pool) the
in-memory branch runs the same two steps WITHOUT a transaction;
both adapters tolerate the absent conn at the type level.

Failure modes per [[project_pii_vault_implementation_design]]:
  - Actor stream missing -> ActorNotFoundError -> 404.
  - DELETE finds 0 rows (already-erased): event still appends; the
    audit trail records distinct operator actions per call.
  - Event append fails after scrub+delete: the WHOLE transaction
    rolls back; MVCC restores the profile row. Caller retries safely.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches the
# convention in cora/infrastructure/postgres/idempotency.py for the same reason.)

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import (
    ActorEvent,
    ProfileStore,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.access.errors import UnauthorizedError
from cora.access.features.forget_actor.command import ForgetActor
from cora.access.features.forget_actor.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Actor"
_COMMAND_NAME = "ForgetActor"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare forget_actor handler — what `bind()` returns.

    See `register_actor.handler.Handler` for the rationale on the
    optional `causation_id` kwarg.
    """

    async def __call__(
        self,
        command: ForgetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """forget_actor handler with Idempotency-Key support.

    Forget is a destructive operation: double-clicking the
    "forget me" button must NOT append two events. The wrapped
    form (built in `wire.py` via `with_idempotency`) caches the
    first response on the Idempotency-Key and replays it for the
    duplicate.
    """

    async def __call__(
        self,
        command: ForgetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a forget_actor handler closed over the shared deps.

    Reads `deps.profile_store` (the shared PII vault adapter) so
    the scrub+delete runs against the SAME instance Access BC and
    Agent BC handlers also use. `deps.pool` is `None` in
    `app_env=test`; the in-memory branch skips the transaction
    block and runs the two steps sequentially (both adapters
    tolerate `conn=None`).
    """

    async def handler(
        command: ForgetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "forget_actor.start",
            command_name=_COMMAND_NAME,
            actor_id=str(command.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "forget_actor.denied",
                command_name=_COMMAND_NAME,
                actor_id=str(command.actor_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.actor_id,
        )
        history: list[ActorEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now)

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.forgotten_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        stream_append = StreamAppend(
            stream_type=_STREAM_TYPE,
            stream_id=command.actor_id,
            expected_version=current_version,
            events=new_events,
        )

        profile_store: ProfileStore = deps.profile_store

        if deps.pool is None:
            # In-memory test path: no transaction (the adapters are
            # synchronous Python dicts). Order matches the Postgres
            # branch — scrub first, then append — so the same
            # retry-safety invariants hold.
            await profile_store.scrub_and_delete(None, command.actor_id)
            await deps.event_store.append_streams([stream_append])
        else:
            async with deps.pool.acquire() as conn, conn.transaction():
                # Scrub-then-delete owns the same transaction as the
                # event append; if append raises ConcurrencyError or
                # any other failure, the scrub+delete rolls back via
                # MVCC and the profile row reappears intact.
                await profile_store.scrub_and_delete(conn, command.actor_id)
                await deps.event_store.append_streams([stream_append], conn=conn)

        _log.info(
            "forget_actor.success",
            command_name=_COMMAND_NAME,
            actor_id=str(command.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
