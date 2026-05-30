# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches
# the convention in cora/calibration/aggregates/calibration/read.py for
# the same reason.)

"""Read repository for the Credential aggregate.

`load_credential(event_store, credential_id) -> Credential | None`
mirrors `load_calibration` / `load_caution` / `load_clearance`. Used
by the federation BC's `get_credential` query slice and by the
rotation / revoke handlers (which pre-load the target Credential
before the decider).

`CredentialLifecycleTimestamps` + `load_credential_timestamps`
mirror the Calibration / Method / Plan Path C precedent
(`project_template_aggregate_timestamps`): lifecycle bookkeeping
timestamps live on the projection, not on the aggregate state, and
read-side surfaces compose Credential + timestamps into a view
DTO at the handler layer.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.federation.aggregates.credential.events import from_stored
from cora.federation.aggregates.credential.evolver import fold
from cora.federation.aggregates.credential.state import Credential
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Credential"

_SELECT_TIMESTAMPS_SQL = """
SELECT registered_at, rotation_started_at
FROM proj_credential_summary
WHERE credential_id = $1
"""


@dataclass(frozen=True)
class CredentialLifecycleTimestamps:
    """Observed wall-clock timestamps for Credential lifecycle events.

    Sourced from `proj_credential_summary`, not from aggregate state.
    `registered_at` is set once on `CredentialRegistered` (the envelope
    `occurred_at` of the genesis event). `rotation_started_at` tracks
    the most recent `CredentialRotationStarted` envelope `occurred_at`
    and is cleared on rotation completion or abort, so the projection
    column is nullable.
    """

    registered_at: datetime
    rotation_started_at: datetime | None


async def load_credential(event_store: EventStore, credential_id: UUID) -> Credential | None:
    """Load and fold a Credential's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, credential_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_credential_timestamps(
    pool: asyncpg.Pool,
    credential_id: UUID,
) -> CredentialLifecycleTimestamps | None:
    """Read the lifecycle-timestamp pair from the projection.

    Contract: `pool` MUST be a live asyncpg pool. The None-check
    belongs to the caller, not this function (mirrors
    `load_calibration_timestamps`). Callers using this from a handler
    should gate on `deps.pool is not None` before invocation; calling
    with a closed or None pool raises an asyncpg runtime error.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, credential_id)  # type: ignore[reportUnknownMemberType]
    if row is None:
        return None
    return CredentialLifecycleTimestamps(
        registered_at=row["registered_at"],
        rotation_started_at=row["rotation_started_at"],
    )
