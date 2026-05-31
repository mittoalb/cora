"""SurfaceActiveVisitProjection: folds Visit control events into the
`proj_trust_surface_active_visit` read model -- the "who drives this
Surface right now?" projection.

Subscribed events:
  - VisitSurfaceControlTaken  -> 2-statement transaction:
      (1) UPDATE prior holder's released_at, then
      (2) INSERT new holder row.
  - VisitSurfaceControlReleased -> UPDATE the open row's released_at.

Take-control must atomically mark the prior holder released + INSERT
the new holder row so the invariant "at most one row per surface with
released_at IS NULL" is preserved without a partial unique index. The
`async with conn.transaction()` block guarantees atomicity at the
projection-worker tier (savepoint within the outer worker transaction).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from asyncpg import Pool

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_SUBSCRIBED: frozenset[str] = frozenset({"VisitSurfaceControlTaken", "VisitSurfaceControlReleased"})

# Statement 1: mark whatever row is currently open on this Surface as
# released at the same instant. The `since_at < $2` predicate is load-
# bearing for replay safety: a stale replay of an OLDER Took event
# must NOT close a NEWER open row. Without it, sequence
# Took(A)@t1 -> Took(B)@t2 followed by a replay of Took(A)@t1 would
# stomp B's row with released_at=t1 (i.e., before B took control).
# Replay-idempotent: second replay of Took(A)@t1 finds either zero
# open rows or only rows with since_at >= $2 and is a no-op.
_TAKE_CONTROL_UPDATE_PRIOR_SQL = """
UPDATE proj_trust_surface_active_visit
SET released_at = $2, updated_at = now()
WHERE surface_id = $1 AND released_at IS NULL AND since_at < $2
"""

# Statement 2: INSERT the new holder. PK includes since_at so re-applying
# the same event finds an existing row and the ON CONFLICT clause makes it
# a no-op.
_TAKE_CONTROL_INSERT_NEW_SQL = """
INSERT INTO proj_trust_surface_active_visit
    (surface_id, visit_id, since_at, released_at)
VALUES ($1, $2, $3, NULL)
ON CONFLICT (surface_id, visit_id, since_at) DO NOTHING
"""

# VisitSurfaceControlReleased: UPDATE the open row's released_at.
# Naturally idempotent: second replay finds zero rows with released_at IS NULL.
_RELEASE_CONTROL_SQL = """
UPDATE proj_trust_surface_active_visit
SET released_at = $3, updated_at = now()
WHERE surface_id = $1 AND visit_id = $2 AND released_at IS NULL
"""

# Read-side: who currently holds this Surface? At most one row with
# released_at IS NULL per surface (invariant maintained by the take-control
# 2-statement transaction above). ORDER BY since_at DESC + LIMIT 1 is
# defensive: if a duplicate replay ever produced two open rows, the most
# recent wins; the partial index makes this a fast index-only scan.
_READ_ACTIVE_HOLDER_SQL = """
SELECT visit_id, since_at
FROM proj_trust_surface_active_visit
WHERE surface_id = $1 AND released_at IS NULL
ORDER BY since_at DESC
LIMIT 1
"""


@dataclass(frozen=True)
class SurfaceActiveVisit:
    """Active controller of a Surface at read time."""

    visit_id: UUID
    since_at: datetime


async def load_surface_active_visit(pool: Pool, surface_id: UUID) -> SurfaceActiveVisit | None:
    """Return the current controlling Visit for a Surface, or None if free.

    Pool MUST be live; None-check belongs to caller. Returns None when no
    open row exists for the surface (free Surface) or when the projection
    has not yet drained the genesis event for the controlling Visit.
    """
    row = await pool.fetchrow(_READ_ACTIVE_HOLDER_SQL, surface_id)
    if row is None:
        return None
    return SurfaceActiveVisit(visit_id=row["visit_id"], since_at=row["since_at"])


class SurfaceActiveVisitProjection:
    """Maintains the `proj_trust_surface_active_visit` read model."""

    name = "proj_trust_surface_active_visit"
    subscribed_event_types = _SUBSCRIBED

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type not in _SUBSCRIBED:
            return

        payload = event.payload
        surface_id = UUID(payload["surface_id"])
        visit_id = UUID(payload["visit_id"])
        occurred_at = datetime.fromisoformat(payload["occurred_at"])

        match event.event_type:
            case "VisitSurfaceControlTaken":
                async with conn.transaction():
                    await conn.execute(_TAKE_CONTROL_UPDATE_PRIOR_SQL, surface_id, occurred_at)
                    await conn.execute(
                        _TAKE_CONTROL_INSERT_NEW_SQL, surface_id, visit_id, occurred_at
                    )
            case "VisitSurfaceControlReleased":
                await conn.execute(_RELEASE_CONTROL_SQL, surface_id, visit_id, occurred_at)
            case _:  # pragma: no cover  # _SUBSCRIBED gate above prevents reaching here
                pass


__all__ = [
    "SurfaceActiveVisit",
    "SurfaceActiveVisitProjection",
    "load_surface_active_visit",
]
