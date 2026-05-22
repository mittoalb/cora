# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Plan aggregate.

`load_plan(event_store, plan_id) -> Plan | None` mirrors
`load_practice` / `load_method` / `load_family` / `load_actor` /
etc. Used by the `get_plan` query slice (6e-1) and any future
update-style commands (6e-2).

`load_plan_timestamps(pool, plan_id) -> PlanLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(Path C). State stays minimal per decider purity
(Chassaing/Pellegrini/Reynhout); lifecycle timestamps live on the
projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Returns None when no projection row exists
(eventual consistency: the row appears after the projection worker
folds PlanDefined; callers should treat the absence as a transient
"projection hasn't caught up yet" rather than "Plan doesn't exist"
— that distinction belongs to `load_plan`). Mirrors
`load_method_timestamps`.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.plan.events import from_stored
from cora.recipe.aggregates.plan.evolver import fold
from cora.recipe.aggregates.plan.state import Plan

_STREAM_TYPE = "Plan"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_recipe_plan_summary
WHERE plan_id = $1
"""


@dataclass(frozen=True)
class PlanLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Plan summary projection, not from aggregate state.
    `created_at` is set once on `PlanDefined`; `versioned_at` is overwritten
    on each `PlanVersioned` (state-always-holds-latest convention mirrored
    in the projection); `deprecated_at` is set once on `PlanDeprecated`
    and is terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_plan(event_store: EventStore, plan_id: UUID) -> Plan | None:
    """Load and fold a Plan's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, plan_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_plan_timestamps(
    pool: asyncpg.Pool,
    plan_id: UUID,
) -> PlanLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`
    and how `make_list_query_handler` is invoked through bound handlers
    that already validated `deps.pool`).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, plan_id)
    if row is None:
        return None
    return PlanLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
