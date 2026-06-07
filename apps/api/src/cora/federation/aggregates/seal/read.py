# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches
# the convention in cora/calibration/aggregates/calibration/read.py for the
# same reason.)

"""Read repository for the Seal aggregate.

`load_seal(event_store, stream_id) -> Seal | None`
mirrors `load_clearance` / `load_calibration`. The Seal is a
per-facility singleton; the handler derives a deterministic stream
UUID from the facility_id (UUID5 with the federation namespace) so
this helper retains the UUID-keyed signature shared across CORA
aggregate read repos. The domain identity that matters
(`Seal.facility_id`) is carried inside the aggregate state.

`SealLifecycleTimestamps` + `load_seal_timestamps` mirror the
Calibration Path C precedent
(`project_template_aggregate_timestamps`): lifecycle bookkeeping
timestamps live on the `proj_federation_seal_summary` projection table, not
on the aggregate state, and read-side surfaces compose Seal +
timestamps into a view DTO at the handler layer.
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
SELECT last_signed_at, last_signed_by
FROM proj_federation_seal_summary
WHERE facility_id = $1
"""


@dataclass(frozen=True)
class SealLifecycleTimestamps:
    """Observed wall-clock metadata for the most recent signing.

    Sourced from `proj_federation_seal_summary`, not from aggregate
    state. `last_signed_at` and `last_signed_by` are `None` until
    the first `SealPointerSigned`; thereafter they reflect the most
    recent signing's `signed_at` payload and `signed_by` (signing
    wall-clock may legitimately differ from event envelope
    `occurred_at`, mirroring Calibration `established_at`).
    `initialized_at` was hoisted onto the aggregate per the
    fold-symmetry Path C reversal; read it from `Seal.initialized_at`.
    """

    last_signed_at: datetime | None
    last_signed_by: UUID | None


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
        last_signed_at=row["last_signed_at"],
        last_signed_by=row["last_signed_by"],
    )
