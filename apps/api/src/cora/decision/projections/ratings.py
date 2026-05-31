"""DecisionRatingsProjection: folds `DecisionRated` events into the
`proj_decision_ratings` read model.

Subscribed events:
  - DecisionRated -> UPSERT one row per (decision_id, rated_by_actor_id)

Latest-per-actor-wins implementation: ON CONFLICT (decision_id,
rated_by_actor_id) DO UPDATE WHERE EXCLUDED.rated_at > rated_at.
The WHERE guard makes the apply() out-of-order-replay safe: if a
projection rebuild lands an older rating after a newer one, the
older one does not overwrite (defensive; production at-least-once
delivery is in-order per stream, but rebuild-from-scratch crosses
streams via the projection-worker advance loop).

`confidence_at_rating` is captured at write time on the
`DecisionRated` event payload (gate-review cross-BC P2-4: the
earlier projection-side denorm pattern would have read
`proj_decision_summary` at apply() time, which races under
rebuild when the summary has not yet caught up with the rated
Decision). The projection simply forwards the captured value into
its column; null when the rated Decision had no confidence value.

`apply()` IS idempotent per the at-least-once delivery contract:
re-applying the same DecisionRated event runs the same UPSERT,
which Postgres handles correctly (latest-rated_at predicate
short-circuits when EXCLUDED.rated_at <= existing rated_at).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_UPSERT_RATING_SQL = """
INSERT INTO proj_decision_ratings
    (decision_id, rated_by_actor_id, rating, comment, rated_at, confidence_at_rating)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (decision_id, rated_by_actor_id) DO UPDATE
   SET rating                   = EXCLUDED.rating,
       comment                  = EXCLUDED.comment,
       rated_at                 = EXCLUDED.rated_at,
       confidence_at_rating  = EXCLUDED.confidence_at_rating
 WHERE EXCLUDED.rated_at > proj_decision_ratings.rated_at
"""


class DecisionRatingsProjection:
    """Maintains the `proj_decision_ratings` read model."""

    name = "proj_decision_ratings"
    subscribed_event_types = frozenset({"DecisionRated"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type != "DecisionRated":
            return
        payload = event.payload
        decision_id = UUID(payload["decision_id"])
        rated_by_actor_id = UUID(payload["rated_by_actor_id"])
        rating = payload["rating"]
        comment = payload.get("comment")
        rated_at = datetime.fromisoformat(payload["rated_at"])
        # Captured by the handler at write time from
        # `Decision.state.confidence`; null when the rated Decision
        # had no confidence value. No cross-projection read; the
        # payload is the single source of truth.
        confidence = payload.get("confidence_at_rating")

        await conn.execute(
            _UPSERT_RATING_SQL,
            decision_id,
            rated_by_actor_id,
            rating,
            comment,
            rated_at,
            confidence,
        )


__all__ = ["DecisionRatingsProjection"]
