"""ZoneSummaryProjection: folds the single ZoneDefined event into
the `proj_trust_zone_summary` read model that backs `GET /zones`.

Subscribed events:
  - ZoneDefined  -> INSERT (id + name + occurred_at)

Zone is immutable-once-defined today (the Defined -> Active ->
Modified -> Archived lifecycle per BC-map is deferred per the
additive-state pattern documented in zone/state.py). Same shape as
the Decision projection: one event, one INSERT, no UPDATE path.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ZONE_SQL = """
INSERT INTO proj_trust_zone_summary
    (zone_id, name, created_at)
VALUES ($1, $2, $3)
ON CONFLICT (zone_id) DO NOTHING
"""


class ZoneSummaryProjection:
    """Maintains the `proj_trust_zone_summary` read model."""

    name = "proj_trust_zone_summary"
    subscribed_event_types = frozenset({"ZoneDefined"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type != "ZoneDefined":
            return
        payload = event.payload
        await conn.execute(
            _INSERT_ZONE_SQL,
            UUID(payload["zone_id"]),
            payload["name"],
            datetime.fromisoformat(payload["occurred_at"]),
        )


__all__ = ["ZoneSummaryProjection"]
