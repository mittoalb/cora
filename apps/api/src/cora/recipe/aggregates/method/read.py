# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Method aggregate.

`load_method(event_store, method_id) -> Method | None` mirrors
`load_family` / `load_actor` / `load_subject` / `load_zone` /
`load_conduit` / `load_policy` / `load_asset`. Used by the
`get_method` query slice (6a) and any future update-style commands
(6b).

`load_method_timestamps(pool, method_id) -> MethodLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(audit-2026-05-20 Iter A, Path C). State stays minimal per decider
purity (Chassaing/Pellegrini/Reynhout); lifecycle timestamps live on
the projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Returns None when no projection row exists
(eventual consistency: the row appears after the projection worker
folds MethodDefined; callers should treat the absence as a transient
"projection hasn't caught up yet" rather than "Method doesn't exist"
— that distinction belongs to `load_method`).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.method.events import from_stored
from cora.recipe.aggregates.method.evolver import fold
from cora.recipe.aggregates.method.state import Method

_STREAM_TYPE = "Method"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_recipe_method_summary
WHERE method_id = $1
"""


@dataclass(frozen=True)
class MethodLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Method summary projection, not from aggregate state.
    `created_at` is set once on `MethodDefined`; `versioned_at` is overwritten
    on each `MethodVersioned` (state-always-holds-latest convention mirrored
    in the projection); `deprecated_at` is set once on `MethodDeprecated`
    and is terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_method(event_store: EventStore, method_id: UUID) -> Method | None:
    """Load and fold a Method's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, method_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_method_timestamps(
    pool: asyncpg.Pool,
    method_id: UUID,
) -> MethodLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors how
    `make_list_query_handler` is invoked through bound handlers that
    already validated `deps.pool`). Callers using this from a handler
    should gate on `deps.pool is not None` before invocation; calling
    with a closed/None pool raises an asyncpg runtime error.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, method_id)
    if row is None:
        return None
    return MethodLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
