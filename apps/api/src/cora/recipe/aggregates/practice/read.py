# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Practice aggregate.

`load_practice(event_store, practice_id) -> Practice | None` mirrors
`load_method` / `load_family` / `load_actor` / etc. Used by the
`get_practice` query slice (6d-1) and any future update-style
commands (6d-2).

`load_practice_timestamps(pool, practice_id) -> PracticeLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(audit-2026-05-20 Iter B-2, Path C). State stays minimal per decider
purity (Chassaing/Pellegrini/Reynhout); lifecycle timestamps live on
the projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Mirrors `load_method_timestamps` /
`load_plan_timestamps`.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.practice.events import from_stored
from cora.recipe.aggregates.practice.evolver import fold
from cora.recipe.aggregates.practice.state import Practice

_STREAM_TYPE = "Practice"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_recipe_practice_summary
WHERE practice_id = $1
"""


@dataclass(frozen=True)
class PracticeLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Practice summary projection, not from aggregate state.
    `created_at` is set once on `PracticeDefined`; `versioned_at` is
    overwritten on each `PracticeVersioned` (state-always-holds-latest
    convention mirrored in the projection); `deprecated_at` is set once on
    `PracticeDeprecated` and is terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_practice(event_store: EventStore, practice_id: UUID) -> Practice | None:
    """Load and fold a Practice's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, practice_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_practice_timestamps(
    pool: asyncpg.Pool,
    practice_id: UUID,
) -> PracticeLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`
    and `load_plan_timestamps`).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, practice_id)
    if row is None:
        return None
    return PracticeLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
