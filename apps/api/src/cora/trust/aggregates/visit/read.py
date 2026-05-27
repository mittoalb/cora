"""Read repository for the Visit aggregate.

`load_visit(event_store, visit_id) -> Visit | None` mirrors `load_policy`
/ `load_campaign`. Used by every non-genesis slice's handler and by
projection-backed read paths that need to load + fold a stream.

`load_visit_timestamps(pool, visit_id) -> VisitLifecycleTimestamps | None`
is the Path C reader for projection-side observable timestamps
(`created_at` / `arrived_at` / `started_at` / `completed_at`). Returned
together with the state by the per-handler `VisitView` wrapper at the
read boundary (Phase beta returns timestamps separately via the
projection table; the wrapper VO is convention-aligned with
`AgentView` / `MethodView` / etc. Path C precedent).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from asyncpg import Pool

from cora.infrastructure.ports import EventStore
from cora.trust.aggregates.visit.events import from_stored
from cora.trust.aggregates.visit.evolver import fold
from cora.trust.aggregates.visit.state import Visit

_STREAM_TYPE = "Visit"


async def load_visit(event_store: EventStore, visit_id: UUID) -> Visit | None:
    """Load and fold a Visit's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, visit_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


@dataclass(frozen=True)
class VisitLifecycleTimestamps:
    """Projection-side observable timestamps for a Visit.

    Path C precedent: `created_at` (genesis), `arrived_at` (Planned ->
    Arrived), `started_at` (Arrived -> InProgress), `completed_at`
    (any terminal: Completed / Cancelled / Aborted / Voided). All
    nullable except `created_at` (genesis always populates created_at).
    Null + populated `status` means projection lag, never missing
    transition (per Path C reader docstring convention).
    """

    created_at: datetime
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


async def load_visit_timestamps(pool: Pool, visit_id: UUID) -> VisitLifecycleTimestamps | None:
    """Load the projection-side lifecycle timestamps for a Visit.

    Pool MUST be live; None-check belongs to caller. Returns None if no
    projection row exists for the visit_id (genesis event not yet
    drained from the event store to the projection worker).
    """
    row = await pool.fetchrow(
        """
        SELECT created_at, arrived_at, started_at, completed_at
        FROM proj_trust_visit_summary
        WHERE visit_id = $1
        """,
        visit_id,
    )
    if row is None:
        return None
    return VisitLifecycleTimestamps(
        created_at=row["created_at"],
        arrived_at=row["arrived_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )
