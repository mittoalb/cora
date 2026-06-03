# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches
# the convention in cora/recipe/aggregates/method/read.py for the same
# reason.)

"""Read repository for the Calibration aggregate.

`load_calibration(event_store, calibration_id) -> Calibration | None`
mirrors `load_caution` / `load_clearance` / `load_asset`. Used by the
`get_calibration` query slice and the `append_calibration_revision` handler (which
pre-loads the target Calibration before the decider).

`CalibrationLifecycleTimestamps` + `load_calibration_timestamps`
mirror the Method / Plan / Family Path C precedent
(`project_template_aggregate_timestamps`): lifecycle bookkeeping
timestamps live on the projection, not on the aggregate state, and
read-side surfaces compose Calibration + timestamps into a view
DTO at the handler layer.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.calibration.aggregates.calibration.events import from_stored
from cora.calibration.aggregates.calibration.evolver import fold
from cora.calibration.aggregates.calibration.state import Calibration
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Calibration"

_SELECT_TIMESTAMPS_SQL = """
SELECT defined_at, last_revised_at
FROM proj_calibration_summary
WHERE calibration_id = $1
"""


@dataclass(frozen=True)
class CalibrationLifecycleTimestamps:
    """Observed wall-clock timestamps for Calibration lifecycle events.

    Sourced from `proj_calibration_summary`, not from aggregate
    state. `defined_at` is set once on `CalibrationDefined` (the
    envelope `occurred_at` of the genesis event); `last_revised_at`
    seeds to the same value and is bumped to each revision's
    `established_at` on every `CalibrationRevisionAppended`.
    """

    defined_at: datetime
    last_revised_at: datetime


async def load_calibration(event_store: EventStore, calibration_id: UUID) -> Calibration | None:
    """Load and fold a Calibration's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, calibration_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_calibration_timestamps(
    pool: asyncpg.Pool,
    calibration_id: UUID,
) -> CalibrationLifecycleTimestamps | None:
    """Read the lifecycle-timestamp pair from the projection.

    Contract: `pool` MUST be a live asyncpg pool — None-check belongs
    to the caller, not this function (mirrors `load_method_timestamps`).
    Callers using this from a handler should gate on `deps.pool is not
    None` before invocation; calling with a closed/None pool raises an
    asyncpg runtime error.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, calibration_id)  # type: ignore[reportUnknownMemberType]
    if row is None:
        return None
    return CalibrationLifecycleTimestamps(
        defined_at=row["defined_at"],
        last_revised_at=row["last_revised_at"],
    )
