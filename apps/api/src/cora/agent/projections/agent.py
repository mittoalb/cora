"""AgentSummaryProjection: folds the Agent aggregate's 3 lifecycle
events into the `proj_agent_summary` read model.

Agent BC's first projection. Built per the Path C lock: state stays
decider-minimal; lifecycle timestamps live on the projection.
Mirrors MethodSummaryProjection + the Plan/Practice/Family/
Capability projections — same state-always-holds-latest convention,
same `(created_at, versioned_at, deprecated_at)` triple, same null
semantics on read-side response composition.

Subscribed events:
  - AgentDefined    -> INSERT (status=Defined,
                               created_at=payload.occurred_at,
                               kind + name + version from payload)
  - AgentVersioned  -> UPDATE status=Versioned + version from payload
                               + versioned_at=payload.occurred_at
                               (overwritten on each re-version — state
                               always holds latest, projection mirrors
                               that)
  - AgentDeprecated -> UPDATE status=Deprecated +
                               deprecated_at=payload.occurred_at

Suspended/Resumed events are intentionally NOT
subscribed: `suspension_reason` is an invariant-bearing field that
deciders read, so it stays on aggregate state. Only the derivable
lifecycle timestamps move to the projection per the audit criterion
("derivable / decider-doesn't-read").

`tools` / `budget` / `capabilities` from the payload are intentionally
NOT projected: they're rich fields, the keyset+filter shape doesn't
need them at LIST time, and a future per-purpose join projection
can carry them when use cases demand "all agents with tool X".
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_AGENT_SQL = """
INSERT INTO proj_agent_summary
    (agent_id, kind, name, version, status, created_at)
VALUES ($1, $2, $3, $4, 'Defined', $5)
ON CONFLICT (agent_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_agent_summary
SET status = 'Versioned',
    version = $2,
    versioned_at = $3,
    updated_at = now()
WHERE agent_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_agent_summary
SET status = 'Deprecated',
    deprecated_at = $2,
    updated_at = now()
WHERE agent_id = $1
"""


class AgentSummaryProjection:
    """Maintains the `proj_agent_summary` read model."""

    name = "proj_agent_summary"
    subscribed_event_types = frozenset(
        {
            "AgentDefined",
            "AgentVersioned",
            "AgentDeprecated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "AgentDefined":
                await conn.execute(
                    _INSERT_AGENT_SQL,
                    UUID(event.payload["agent_id"]),
                    event.payload["kind"],
                    event.payload["name"],
                    event.payload["version"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AgentVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["agent_id"]),
                    event.payload["version"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AgentDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["agent_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case _:
                pass


__all__ = ["AgentSummaryProjection"]
