"""ActorSummaryProjection: folds Actor lifecycle events into the
`proj_access_actor_summary` read model that backs `GET /actors`.

Subscribed events:
  - ActorRegistered -> INSERT a row at status='active'
  - ActorDeactivated -> UPDATE status to 'deactivated'

Both apply branches are idempotent (the framework delivers at-least-
once; re-applying the same event must produce the same row state):

  - INSERT uses `ON CONFLICT (actor_id) DO NOTHING` so re-application
    of the same `ActorRegistered` is a no-op.
  - UPDATE writes the same `status='deactivated'` value regardless of
    how many times the event lands; idempotent by construction.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ACTOR_SQL = """
INSERT INTO proj_access_actor_summary
    (actor_id, name, kind, status, created_at)
VALUES ($1, $2, $3, 'active', $4)
ON CONFLICT (actor_id) DO NOTHING
"""

_DEACTIVATE_ACTOR_SQL = """
UPDATE proj_access_actor_summary
SET status = 'deactivated', updated_at = now()
WHERE actor_id = $1
"""


class ActorSummaryProjection:
    """Maintains the `proj_access_actor_summary` read model.

    `name` and `subscribed_event_types` are class-level constants
    (not ClassVar-annotated, matching the Projection Protocol's
    plain-attr declaration). Python semantics are identical to
    ClassVar for these immutable values.
    """

    name = "proj_access_actor_summary"
    subscribed_event_types = frozenset({"ActorRegistered", "ActorDeactivated"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        """Dispatch on event_type. Both branches are idempotent.

        The worker's advance query filters by
        `event_type = ANY($subscribed_event_types)` so apply() never
        sees unsubscribed types in production. The bare `case _: pass`
        below is for pyright exhaustiveness on `str`, not defensive
        runtime logic — a future projection author who adds an event
        type to `subscribed_event_types` without adding a match arm
        will see missing rows in the projection table (loud and easy
        to debug), not silent corruption.
        """
        match event.event_type:
            case "ActorRegistered":
                # `kind` is forward-compat: pre-8f-a payloads lack it,
                # so `payload.get("kind", "human")` matches the
                # `from_stored` deserializer's default.
                await conn.execute(
                    _INSERT_ACTOR_SQL,
                    UUID(event.payload["actor_id"]),
                    event.payload["name"],
                    event.payload.get("kind", "human"),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "ActorDeactivated":
                await conn.execute(
                    _DEACTIVATE_ACTOR_SQL,
                    UUID(event.payload["actor_id"]),
                )
            case _:
                pass


__all__ = ["ActorSummaryProjection"]
