# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Family aggregate.

`load_family(event_store, family_id) -> Family | None` mirrors
`load_actor` / `load_subject` / `load_zone` / etc.

`load_family_timestamps(pool, family_id) -> FamilyLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(audit-2026-05-20 Iter B-3, Path C). State stays minimal per decider
purity (Chassaing/Pellegrini/Reynhout); lifecycle timestamps live on
the projection per Dudycz pragmatic-redundancy + K8s/GitHub/AIP-142
resource-API precedent. Mirrors `load_method_timestamps` /
`load_plan_timestamps` / `load_practice_timestamps`.

## Stream type after rename

`_STREAM_TYPE = "Family"`. The stream-type string is the event store's
internal categorization key. CORA is greenfield (no production
deployments at 5i lock time), so changing the stream key to match the
new aggregate name is the simpler choice; if a future deployment ever
needs to read pre-5i streams written under the old `"Capability"`
stream type, add a one-time migration that updates `events.stream_type`
to `"Family"` (the event payloads themselves stay untouched per
[[project-immutability-guarantee]]; only the categorization label
changes). Watch item documented in DLM-A.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.equipment.aggregates.family.events import from_stored
from cora.equipment.aggregates.family.evolver import fold
from cora.equipment.aggregates.family.state import Family
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Family"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_equipment_family_summary
WHERE family_id = $1
"""


@dataclass(frozen=True)
class FamilyLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Family summary projection, not from aggregate state.
    `created_at` is set once on `(Family|Capability)Defined`; `versioned_at`
    is overwritten on each `(Family|Capability)Versioned` (state-always-
    holds-latest convention mirrored in the projection); `deprecated_at`
    is set once on `(Family|Capability)Deprecated` and is terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_family(event_store: EventStore, family_id: UUID) -> Family | None:
    """Load and fold a Family's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, family_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_family_timestamps(
    pool: asyncpg.Pool,
    family_id: UUID,
) -> FamilyLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`
    and peers).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, family_id)
    if row is None:
        return None
    return FamilyLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
