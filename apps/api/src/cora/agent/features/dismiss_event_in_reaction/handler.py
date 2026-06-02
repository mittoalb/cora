"""Application handler for the `dismiss_event_in_reaction` slice.

Atomic two-write recovery action: when an operator confirms a poison
event is stuck on a Reaction's bookmark, this handler advances the
`projection_bookmarks` row past it AND records the dismissal as a
`DecisionRegistered` (context `ReactionDismissal`) in the same
Postgres transaction. Mirrors the `forget_actor` cross-store pattern
(non-event SQL write inside the same `conn.transaction()` that the
event_store.append_streams call shares).

In-memory mode (no Postgres pool) raises
`DismissalRequiresPostgresError` because the `projection_bookmarks`
table is the load-bearing structure; the in-memory event store has no
equivalent and a Decision-only write would be misleading.

Pre-load order (handler-side I/O):

  1. Read the bookmark row FOR UPDATE (locks against concurrent
     advance from the projection worker so the bookmark cursor we
     read is the one we update).
  2. Read the target event by `event_id` to resolve its
     (transaction_id, position) cursor and event_type.
  3. Hand both to the pure decider.

Authorization runs BEFORE the transaction so a deny short-circuits
without acquiring a pool connection.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Protocol
from uuid import UUID

from cora.agent.errors import (
    DismissalEventNotFoundError,
    DismissalRequiresPostgresError,
    SubscriberBookmarkNotFoundError,
    UnauthorizedError,
)
from cora.agent.features.dismiss_event_in_reaction.command import (
    DismissEventInReaction,
)
from cora.agent.features.dismiss_event_in_reaction.decider import (
    DismissalContext,
    decide,
)
from cora.decision.aggregates.decision import (
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "DismissEventInReaction"

_log = get_logger(__name__)

# Read the bookmark cursor + lock the row so concurrent advance from
# the projection worker cannot move the cursor between our read and
# our update.
_READ_BOOKMARK_SQL = """
SELECT last_transaction_id::text AS last_tx, last_position
FROM projection_bookmarks
WHERE name = $1
FOR UPDATE
"""

# Resolve the event's cursor + type. UUID lookup hits the
# `events_event_id_idx` UNIQUE index added with the events table.
_LOAD_EVENT_SQL = """
SELECT transaction_id::text AS transaction_id_text,
       position,
       event_type,
       recorded_at
FROM events
WHERE event_id = $1
"""

# Advance the bookmark to the dismissed event's cursor; reset
# failure-tracking columns (the dismissal is a successful operator
# resolution, so consecutive_failures resets to 0 just like a
# normal advance). Same shape as `_WRITE_BOOKMARK_SQL` in
# infrastructure/projection/bookmark.py.
_ADVANCE_BOOKMARK_SQL = """
UPDATE projection_bookmarks
SET last_transaction_id    = $2::xid8,
    last_position          = $3,
    last_event_recorded_at = $4,
    last_error_at          = NULL,
    last_error_message     = NULL,
    consecutive_failures   = 0,
    updated_at             = now()
WHERE name = $1
"""


class Handler(Protocol):
    """Callable interface every dismiss_event_in_reaction handler implements."""

    async def __call__(
        self,
        command: DismissEventInReaction,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a dismiss_event_in_reaction handler closed over `deps`."""

    async def handler(
        command: DismissEventInReaction,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "dismiss_event_in_reaction.start",
            command_name=_COMMAND_NAME,
            subscriber_name=command.subscriber_name,
            event_id=str(command.event_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "dismiss_event_in_reaction.denied",
                command_name=_COMMAND_NAME,
                subscriber_name=command.subscriber_name,
                event_id=str(command.event_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        if deps.pool is None:
            raise DismissalRequiresPostgresError()

        new_decision_id = deps.id_generator.new_id()
        now = deps.clock.now()

        async with deps.pool.acquire() as conn, conn.transaction():
            bookmark_row = await conn.fetchrow(_READ_BOOKMARK_SQL, command.subscriber_name)
            if bookmark_row is None:
                raise SubscriberBookmarkNotFoundError(command.subscriber_name)
            bookmark_tx = int(bookmark_row["last_tx"])
            bookmark_pos = int(bookmark_row["last_position"])

            event_row = await conn.fetchrow(_LOAD_EVENT_SQL, command.event_id)
            if event_row is None:
                raise DismissalEventNotFoundError(command.event_id)

            context = DismissalContext(
                bookmark_transaction_id=bookmark_tx,
                bookmark_position=bookmark_pos,
                event_transaction_id=int(event_row["transaction_id_text"]),
                event_position=int(event_row["position"]),
                event_type=str(event_row["event_type"]),
                event_recorded_at=event_row["recorded_at"],
            )

            domain_event = decide(
                None,
                command,
                context=context,
                new_decision_id=new_decision_id,
                principal_id=principal_id,
                now=now,
            )

            new_event = to_new_event(
                event_type=event_type_name(domain_event),
                payload=to_payload(domain_event),
                occurred_at=domain_event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )

            await conn.execute(
                _ADVANCE_BOOKMARK_SQL,
                command.subscriber_name,
                context.event_transaction_id,
                context.event_position,
                context.event_recorded_at,
            )

            await deps.event_store.append_streams(
                [
                    StreamAppend(
                        stream_type=_STREAM_TYPE,
                        stream_id=new_decision_id,
                        expected_version=0,
                        events=[new_event],
                    )
                ],
                conn=conn,
            )

        _log.info(
            "dismiss_event_in_reaction.success",
            command_name=_COMMAND_NAME,
            subscriber_name=command.subscriber_name,
            event_id=str(command.event_id),
            decision_id=str(new_decision_id),
            advanced_to_transaction_id=context.event_transaction_id,
            advanced_to_position=context.event_position,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )
        return new_decision_id

    return handler
