# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Capability aggregate.

`load_capability(event_store, capability_id) -> Capability | None`
mirrors `load_family` / `load_method` / `load_plan` / etc.

`load_capability_timestamps(pool, capability_id) -> CapabilityLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(Path C). State stays minimal per decider purity
(Chassaing/Pellegrini/Reynhout); lifecycle timestamps live on the
projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Mirrors `load_method_timestamps` /
`load_plan_timestamps` / `load_practice_timestamps` /
`load_family_timestamps`.

Note: `Capability.replaced_by_capability_id` STATE field (catalog
governance per [[project-capability-aggregate-design]]) is
unaffected — it's an intrinsic deprecation pointer that the decider
may read on future commands, distinct from the lifecycle-when
timestamp surfaced here.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.capability.events import from_stored
from cora.recipe.aggregates.capability.evolver import fold
from cora.recipe.aggregates.capability.state import Capability

_STREAM_TYPE = "Capability"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_recipe_capability_summary
WHERE capability_id = $1
"""


@dataclass(frozen=True)
class CapabilityLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Recipe.Capability summary projection, not from
    aggregate state. `created_at` is set once on `RecipeCapabilityDefined`;
    `versioned_at` is overwritten on each `RecipeCapabilityVersioned`
    (state-always-holds-latest convention mirrored in the projection);
    `deprecated_at` is set once on `RecipeCapabilityDeprecated` and is
    terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_capability(event_store: EventStore, capability_id: UUID) -> Capability | None:
    """Load and fold a Capability's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, capability_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_capability_timestamps(
    pool: asyncpg.Pool,
    capability_id: UUID,
) -> CapabilityLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`
    and peers).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, capability_id)
    if row is None:
        return None
    return CapabilityLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
