"""CampaignSummaryProjection: folds the Campaign aggregate's events into
the `proj_campaign_summary` read model that backs
`GET /campaigns`.

Subscribed events:
  - CampaignRegistered -> INSERT (status='Planned', started_at=NULL,
                                  last_status_*=NULL, run_count=0)
  - CampaignStarted    -> UPDATE status='Active' + started_at
                                 + last_status_changed_at
  - CampaignHeld       -> UPDATE status='Held' + last_status_reason
                                 + last_status_changed_at
  - CampaignResumed    -> UPDATE status='Active'
                                 + last_status_changed_at
                                 (last_status_reason PRESERVED)
  - CampaignClosed     -> UPDATE status='Closed'
                                 + last_status_changed_at
  - CampaignAbandoned  -> UPDATE status='Abandoned'
                                 + last_status_reason
                                 + last_status_changed_at

## Anti-hooks pinned at the projection layer

  - Anti-hook (no auto-notification). The projection is a pull-on-read
    read model; nothing else is written when a new campaign lands.
  - Anti-hook (no cascade). Campaign state changes never touch member
    Run state; the projection has no Run-side coupling.
  - The projection does NOT include `external_refs` (lives on the
    aggregate stream; per design memo §12 the projection columns include
    `external_id` only, not `external_refs`). Reverse-query "Campaigns
    by external_ref scheme/value" is a Watch item.
  - The projection does NOT include `run_ids` (full set lives on the
    aggregate stream; `run_count` is the only denorm). Reverse-query
    "Campaigns containing run X" is Watch item #10 (needs Run.campaign_id
    indexed scan on proj_run_summary).

## SAVEPOINT semantics on CampaignRegistered

The INSERT is wrapped in `async with conn.transaction(): ...` so any
future cross-stream uniqueness violation (today there is no UNIQUE
INDEX; campaign_id PK alone is sufficient and idempotent via
`ON CONFLICT (campaign_id) DO NOTHING`) would roll back only the inner
SAVEPOINT. The supply projection's pattern is reused verbatim for
forward-compat even though the failure mode is narrower here.

## Started_at semantics

`started_at` is set on the FIRST CampaignStarted only (Planned ->
Active transition). Per design memo: CampaignStarted is the
single-source genesis transition (decider gates source to Planned).
CampaignResumed (Held -> Active) does NOT touch `started_at`: the
first-start timestamp is preserved as audit truth for "when did this
campaign begin work" and is not the same concept as "resumed".

## Last_status_reason preservation on resume

CampaignResumed does NOT clear `last_status_reason`. Per design memo:
"Keep it -- audit value". The breadcrumb "why was it held before the
resume" stays readable after the resume lands.

## Run_count

`run_count` is denormalized from the Campaign aggregate's
`run_ids: frozenset[UUID]` (full set lives on the aggregate stream;
`get_campaign` returns the full set from aggregate state). Maintained
by 6i-c arms:

  - CampaignRunAdded   -> run_count = run_count + 1
  - CampaignRunRemoved -> run_count = run_count - 1

The events are written by the cross-aggregate `add_run_to_campaign` /
`remove_run_from_campaign` slices (and by `start_run` when
`StartRun.campaign_id` is provided -- atomic with `RunStarted` via
`EventStore.append_streams`). Out-of-order processing is not a concern:
the worker processes events in (transaction_id, position) order, so
`CampaignRunAdded` cannot arrive before its parent
`CampaignRegistered` for the same campaign_id.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CAMPAIGN_SQL = """
INSERT INTO proj_campaign_summary
    (campaign_id, name, intent, status, lead_actor_id, subject_id,
     description, tags, external_id, run_count, registered_at,
     started_at, last_status_changed_at, last_status_reason)
VALUES ($1, $2, $3, 'Planned', $4, $5,
        $6, $7::text[], $8, 0, $9,
        NULL, NULL, NULL)
ON CONFLICT (campaign_id) DO NOTHING
"""

_UPDATE_STARTED_SQL = """
UPDATE proj_campaign_summary
SET status = 'Active',
    started_at = $2,
    last_status_changed_at = $2,
    updated_at = now()
WHERE campaign_id = $1
"""

_UPDATE_HELD_SQL = """
UPDATE proj_campaign_summary
SET status = 'Held',
    last_status_reason = $2,
    last_status_changed_at = $3,
    updated_at = now()
WHERE campaign_id = $1
"""

_UPDATE_RESUMED_SQL = """
UPDATE proj_campaign_summary
SET status = 'Active',
    last_status_changed_at = $2,
    updated_at = now()
WHERE campaign_id = $1
"""

_UPDATE_CLOSED_SQL = """
UPDATE proj_campaign_summary
SET status = 'Closed',
    last_status_changed_at = $2,
    updated_at = now()
WHERE campaign_id = $1
"""

_UPDATE_ABANDONED_SQL = """
UPDATE proj_campaign_summary
SET status = 'Abandoned',
    last_status_reason = $2,
    last_status_changed_at = $3,
    updated_at = now()
WHERE campaign_id = $1
"""

_UPDATE_RUN_ADDED_SQL = """
UPDATE proj_campaign_summary
SET run_count = run_count + 1,
    updated_at = now()
WHERE campaign_id = $1
"""

# N12 gate-review nit: defensive floor guard on the decrement. The
# `run_count > 0` predicate in the WHERE clause prevents an underflow
# from ever materializing as a negative count even if a duplicate
# CampaignRunRemoved arrives (worker re-delivery, replay) or the
# event-side decider's idempotency invariant ever slips. A negative
# run_count would be a silent integrity bug on the read model; the
# guard turns it into a no-op decrement instead. Preferred over a
# table-level CHECK (run_count >= 0) constraint because (a) no new
# migration is needed and (b) a CHECK violation would block the
# projection worker on the bad event forever.
_UPDATE_RUN_REMOVED_SQL = """
UPDATE proj_campaign_summary
SET run_count = run_count - 1,
    updated_at = now()
WHERE campaign_id = $1
  AND run_count > 0
"""


class CampaignSummaryProjection:
    """Maintains the `proj_campaign_summary` read model."""

    name = "proj_campaign_summary"
    subscribed_event_types = frozenset(
        {
            "CampaignRegistered",
            "CampaignStarted",
            "CampaignHeld",
            "CampaignResumed",
            "CampaignClosed",
            "CampaignAbandoned",
            # membership arms maintain run_count denormalization.
            "CampaignRunAdded",
            "CampaignRunRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "CampaignRegistered":
            payload = event.payload
            raw_subject = payload.get("subject_id")
            raw_external_id = payload.get("external_id")
            # Wrap in SAVEPOINT mirroring the supply projection's
            # forward-compat pattern; the PK alone makes the INSERT
            # idempotent today, but a future cross-stream uniqueness
            # constraint would otherwise stall the worker on duplicate.
            async with conn.transaction():
                await conn.execute(
                    _INSERT_CAMPAIGN_SQL,
                    UUID(payload["campaign_id"]),
                    payload["name"],
                    payload["intent"],
                    UUID(payload["lead_actor_id"]),
                    UUID(raw_subject) if raw_subject is not None else None,
                    payload.get("description"),
                    list(payload.get("tags", [])),
                    raw_external_id,
                    datetime.fromisoformat(payload["occurred_at"]),
                )
            return

        if event.event_type == "CampaignStarted":
            await conn.execute(
                _UPDATE_STARTED_SQL,
                UUID(event.payload["campaign_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "CampaignHeld":
            await conn.execute(
                _UPDATE_HELD_SQL,
                UUID(event.payload["campaign_id"]),
                event.payload["reason"],
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "CampaignResumed":
            await conn.execute(
                _UPDATE_RESUMED_SQL,
                UUID(event.payload["campaign_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "CampaignClosed":
            await conn.execute(
                _UPDATE_CLOSED_SQL,
                UUID(event.payload["campaign_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "CampaignAbandoned":
            await conn.execute(
                _UPDATE_ABANDONED_SQL,
                UUID(event.payload["campaign_id"]),
                event.payload["reason"],
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "CampaignRunAdded":
            # membership add. Increments run_count denorm.
            # Status / last_status_reason unchanged (membership mutations
            # are NOT status transitions per design memo lock).
            await conn.execute(
                _UPDATE_RUN_ADDED_SQL,
                UUID(event.payload["campaign_id"]),
            )
            return

        if event.event_type == "CampaignRunRemoved":
            # membership remove. Decrements run_count denorm.
            # `reason` lives only on the event payload (per-membership
            # audit breadcrumb); does NOT update last_status_reason.
            await conn.execute(
                _UPDATE_RUN_REMOVED_SQL,
                UUID(event.payload["campaign_id"]),
            )
            return

        # Unsubscribed event type (defensive; the worker shouldn't deliver
        # foreign event types given subscribed_event_types).
        return


__all__ = ["CampaignSummaryProjection"]
