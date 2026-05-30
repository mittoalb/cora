# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches
# the convention in cora/calibration/aggregates/calibration/read.py for the
# same reason.)

"""Read repository for the Seal aggregate.

`load_seal(event_store, stream_id) -> Seal | None`
mirrors `load_clearance` / `load_calibration`. The Seal is a
per-facility singleton; the Stage-2 handler derives a deterministic
stream UUID from the facility_id (UUID5 with the federation namespace)
so this helper retains the UUID-keyed signature shared across CORA
aggregate read repos. The domain identity that matters
(`Seal.facility_id`) is carried inside the aggregate state.

`SealLifecycleTimestamps` + `load_seal_timestamps`
mirror the Calibration Path C precedent
(`project_template_aggregate_timestamps`): lifecycle bookkeeping
timestamps live on the projection, not on the aggregate state, and
read-side surfaces compose Seal + timestamps into a view DTO
at the handler layer. Stage 2 introduces the projection table
(`proj_federation_seal`) that backs this view.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.federation.aggregates.seal.events import from_stored
from cora.federation.aggregates.seal.evolver import fold
from cora.federation.aggregates.seal.state import Seal
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Seal"

_SELECT_TIMESTAMPS_SQL = """
SELECT initialized_at, last_signed_at, last_signed_by_actor_id
FROM proj_federation_seal
WHERE facility_id = $1
"""


@dataclass(frozen=True)
class SealLifecycleTimestamps:
    """Observed wall-clock timestamps for Seal lifecycle events.

    Sourced from `proj_federation_seal`, not from aggregate
    state. `initialized_at` is set once on `SealInitialized`
    (the envelope `occurred_at` of the genesis event).
    `last_signed_at` and `last_signed_by_actor_id` are `None` until
    the first `SealPointerSigned`; thereafter they reflect the
    most recent signing's `signed_at` payload and `signed_by_actor_id`
    (signing wall-clock may legitimately differ from event envelope
    `occurred_at`, mirroring Calibration `established_at`).
    """

    initialized_at: datetime
    last_signed_at: datetime | None
    last_signed_by_actor_id: UUID | None


async def load_seal(event_store: EventStore, stream_id: UUID) -> Seal | None:
    """Load and fold a Seal's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, stream_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_seal_timestamps(
    pool: asyncpg.Pool,
    facility_id: str,
) -> SealLifecycleTimestamps | None:
    """Read the lifecycle-timestamp tuple from the projection.

    Contract: `pool` MUST be a live asyncpg pool; None-check belongs
    to the caller, not this function (mirrors `load_calibration_timestamps`).
    Callers using this from a handler should gate on `deps.pool is not
    None` before invocation; calling with a closed/None pool raises an
    asyncpg runtime error.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, facility_id)  # type: ignore[reportUnknownMemberType]
    if row is None:
        return None
    return SealLifecycleTimestamps(
        initialized_at=row["initialized_at"],
        last_signed_at=row["last_signed_at"],
        last_signed_by_actor_id=row["last_signed_by_actor_id"],
    )
