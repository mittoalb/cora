"""ConduitSummaryProjection: folds the ConduitDefined event into the
`proj_trust_conduit_summary` read model that backs `GET /conduits`.

Subscribed events:
  - ConduitDefined  -> INSERT (id + name + source_zone_id +
                               target_zone_id + occurred_at)

ConduitLogbookOpened/Closed events are intentionally NOT subscribed:
they are internal logbook bookkeeping (the entries store carries
traversal rows; the aggregate-level logbook events are for the
audit trail, not the summary projection). Same precedent as the
Decision summary projection skipping its DecisionLogbookOpened/Closed
events. A future `proj_trust_conduit_logbooks` join projection
covers "list conduits with N+ traversals in window" if that use
case crystallizes.

Conduit is immutable-once-defined for Phase 8e-8 (lifecycle
additions deferred per the additive-state pattern in
conduit/state.py).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CONDUIT_SQL = """
INSERT INTO proj_trust_conduit_summary
    (conduit_id, name, source_zone_id, target_zone_id, created_at)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (conduit_id) DO NOTHING
"""


class ConduitSummaryProjection:
    """Maintains the `proj_trust_conduit_summary` read model."""

    name = "proj_trust_conduit_summary"
    subscribed_event_types = frozenset({"ConduitDefined"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type != "ConduitDefined":
            return
        payload = event.payload
        await conn.execute(
            _INSERT_CONDUIT_SQL,
            UUID(payload["conduit_id"]),
            payload["name"],
            UUID(payload["source_zone_id"]),
            UUID(payload["target_zone_id"]),
            datetime.fromisoformat(payload["occurred_at"]),
        )


__all__ = ["ConduitSummaryProjection"]
