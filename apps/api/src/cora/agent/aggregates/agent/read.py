# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Agent aggregate.

`load_agent(event_store, agent_id) -> Agent | None` mirrors
`load_actor` / `load_caution` / `load_supply`. Used by the
`get_agent` query slice and the update-style handlers
(`version_agent` and `deprecate_agent` load the target Agent before
the decider).

`load_agent_timestamps(pool, agent_id) -> AgentLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(audit-2026-05-20 Iter C-2, Path C). State stays decider-minimal
per Chassaing/Pellegrini/Reynhout; lifecycle timestamps live on the
projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Mirrors `load_method_timestamps` and the
other 4 Iter B aggregates.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.agent.aggregates.agent.events import from_stored
from cora.agent.aggregates.agent.evolver import fold
from cora.agent.aggregates.agent.state import Agent
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Agent"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_agent_summary
WHERE agent_id = $1
"""


@dataclass(frozen=True)
class AgentLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Agent summary projection, not from aggregate state.
    `created_at` is set once on `AgentDefined`; `versioned_at` is
    overwritten on each `AgentVersioned` (state-always-holds-latest
    convention mirrored in the projection); `deprecated_at` is set
    once on `AgentDeprecated` and is terminal.

    Suspended/Resumed timestamps are intentionally NOT here — they
    stay on aggregate state because `suspension_reason` is invariant-
    bearing (deciders read it). Only the derivable lifecycle
    timestamps move to the projection per the audit-2026-05-20
    criterion.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_agent(event_store: EventStore, agent_id: UUID) -> Agent | None:
    """Load and fold an Agent's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, agent_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_agent_timestamps(
    pool: asyncpg.Pool,
    agent_id: UUID,
) -> AgentLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`
    and peers).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, agent_id)
    if row is None:
        return None
    return AgentLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
