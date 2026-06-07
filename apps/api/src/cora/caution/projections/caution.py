"""CautionSummaryProjection: folds the Caution aggregate's events into
the `proj_caution_summary` read model that backs `GET /cautions`.

Subscribed events:
  - CautionRegistered  -> INSERT (status='Active', last_status_changed_at=NULL,
                                  superseded_by_caution_id=NULL,
                                  retired_reason=NULL,
                                  parent_id=<None for top-level;
                                             UUID for supersession child>)
  - CautionSuperseded  -> UPDATE status='Superseded'
                                 + superseded_by_caution_id
                                 + last_status_changed_at
  - CautionRetired     -> UPDATE status='Retired'
                                 + retired_reason
                                 + last_status_changed_at

## Anti-hooks pinned at the projection layer

  - Anti-pattern #6 (no outbox / no notification on CautionRegistered).
    The projection is a pull-on-read read model; nothing else is written
    when a new caution lands. Run.start consumes via the future
    CautionLookup port (11b-c), not via push.
  - Anti-pattern #9 (no category exhaustiveness on read). Unknown
    category values still flow through the SQL CHECK constraint at the
    table level; the projection does not add a second filter layer. If
    the constraint ever loosens (additive StrEnum), the projection
    keeps working without redeployment.

## SAVEPOINT semantics on CautionRegistered

The INSERT is wrapped in `async with conn.transaction(): ...` so any
future cross-stream uniqueness violation (today there is no UNIQUE
INDEX; caution_id PK alone is sufficient and idempotent via `ON CONFLICT
(caution_id) DO NOTHING`) would roll back only the inner SAVEPOINT.
The supply projection's pattern is reused verbatim for forward-compat
even though the failure mode is narrower here.

## Supersession child genesis

The `CautionRegistered` arm reads `parent_id` from the payload
unconditionally: `None` for top-level registers, a UUID for the
supersession child genesis written atomically alongside the parent's
`CautionSuperseded` (via `EventStore.append_streams`). The child's
parent-pointer + the parent's `superseded_by_caution_id` together form
the supersession lineage chain.

## Propagate_to_children: hint-only today

`propagate_to_children` is stored as-is on the projection row. The
column does NOT trigger any walk over `Asset.parent_id` at projection
time (Watch item #8); 11b-b ships read-as-stored only. Future Asset-
hierarchy propagation lands as either a denorm projection (cautions
inherited downward) or query-time join, whichever the consumer pulls
for first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CAUTION_SQL = """
INSERT INTO proj_caution_summary
    (caution_id, target_kind, target_id, category, severity, text, workaround,
     authored_by, tags, expires_at, propagate_to_children,
     status, parent_id, superseded_by_caution_id, retired_reason,
     registered_at, last_status_changed_at)
VALUES ($1, $2, $3, $4, $5, $6, $7,
        $8, $9::text[], $10, $11,
        'Active', $12, NULL, NULL,
        $13, NULL)
ON CONFLICT (caution_id) DO NOTHING
"""

_UPDATE_SUPERSEDED_SQL = """
UPDATE proj_caution_summary
SET status = 'Superseded',
    superseded_by_caution_id = $2,
    last_status_changed_at = $3,
    updated_at = now()
WHERE caution_id = $1
"""

_UPDATE_RETIRED_SQL = """
UPDATE proj_caution_summary
SET status = 'Retired',
    retired_reason = $2,
    last_status_changed_at = $3,
    updated_at = now()
WHERE caution_id = $1
"""


class CautionSummaryProjection:
    """Maintains the `proj_caution_summary` read model."""

    name = "proj_caution_summary"
    subscribed_event_types = frozenset(
        {
            "CautionRegistered",
            "CautionSuperseded",
            "CautionRetired",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "CautionRegistered":
            payload = event.payload
            target = payload["target"]
            raw_expires_at = payload.get("expires_at")
            raw_parent = payload.get("parent_id")
            # Wrap in SAVEPOINT mirroring the supply projection's
            # forward-compat pattern; the PK alone makes the INSERT
            # idempotent today, but a future cross-stream uniqueness
            # constraint would otherwise stall the worker on duplicate.
            async with conn.transaction():
                await conn.execute(
                    _INSERT_CAUTION_SQL,
                    UUID(payload["caution_id"]),
                    target["kind"],
                    UUID(target["id"]),
                    payload["category"],
                    payload["severity"],
                    payload["text"],
                    payload["workaround"],
                    UUID(payload["authored_by"]),
                    list(payload["tags"]),
                    (
                        datetime.fromisoformat(raw_expires_at)
                        if raw_expires_at is not None
                        else None
                    ),
                    payload.get("propagate_to_children", False),
                    UUID(raw_parent) if raw_parent is not None else None,
                    datetime.fromisoformat(payload["occurred_at"]),
                )
            return

        if event.event_type == "CautionSuperseded":
            await conn.execute(
                _UPDATE_SUPERSEDED_SQL,
                UUID(event.payload["caution_id"]),
                UUID(event.payload["superseded_by_caution_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "CautionRetired":
            await conn.execute(
                _UPDATE_RETIRED_SQL,
                UUID(event.payload["caution_id"]),
                event.payload["reason"],
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        # Unsubscribed event type (defensive; the worker shouldn't deliver
        # foreign event types given subscribed_event_types).
        return


__all__ = ["CautionSummaryProjection"]
