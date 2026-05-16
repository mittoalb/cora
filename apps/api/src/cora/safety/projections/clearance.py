"""ClearanceSummaryProjection: folds the Clearance aggregate's events
into the `proj_safety_clearance_summary` read model that backs
`GET /clearances`.

Subscribed events:
  - ClearanceRegistered          -> INSERT (status='Defined', last_status_*=NULL,
                                            last_reviewed_by_actor_id=NULL)
  - ClearanceSubmitted           -> UPDATE status='Submitted'   + status-change ts
  - ClearanceReviewStarted       -> UPDATE status='UnderReview' + status-change ts
  - ClearanceReviewStepAppended  -> NO-OP (review_steps chain lives on aggregate
                                           stream only; not surfaced in list view)
  - ClearanceApproved            -> UPDATE status='Approved'
                                          + status-change ts
                                          + last_reviewed_by_actor_id (read from
                                            StoredEvent.principal_id envelope)
                                          + valid_from / valid_until (if provided)
  - ClearanceRejected            -> UPDATE status='Rejected'
                                          + status-change ts
                                          + last_status_reason
                                          + last_reviewed_by_actor_id (read from
                                            StoredEvent.principal_id envelope)
  - ClearanceActivated           -> UPDATE status='Active'     + status-change ts

The Approved/Rejected arms denormalize `last_reviewed_by_actor_id`
from the event envelope (`StoredEvent.principal_id`) rather than the
payload. The aggregate state itself no longer carries
`last_reviewed_by_actor_id` (per actor-id-duplication cleanup in
11a-c-1); the projection column remains for list-view queries.

11a-c will add `ClearanceExpired` and `ClearanceSuperseded` arms; the
status CHECK constraint already accommodates them (locked 8-value day-1).

The projection deliberately subscribes to ClearanceReviewStepAppended
but emits no SQL: that keeps the worker's subscription set complete
(per the architecture invariant that subscribed_event_types lists
every event the consumer cares about, even no-op cases) without
denormalizing the review_steps chain into the projection. Operators that
need the chain fetch the aggregate via `get_clearance`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from typing import Any
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CLEARANCE_SQL = """
INSERT INTO proj_safety_clearance_summary
    (clearance_id, kind, facility_asset_id, title, external_id, status,
     risk_band,
     subject_binding_ids, asset_binding_ids, run_binding_ids, procedure_binding_ids,
     parent_clearance_id, registered_at,
     last_status_changed_at, last_status_reason, last_reviewed_by_actor_id,
     valid_from, valid_until, next_review_due_at)
VALUES ($1, $2, $3, $4, $5, 'Defined',
        $6,
        $7::uuid[], $8::uuid[], $9::uuid[], $10::uuid[],
        $11, $12,
        NULL, NULL, NULL,
        $13, $14, NULL)
ON CONFLICT (clearance_id) DO NOTHING
"""

_UPDATE_SUBMITTED_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'Submitted',
    last_status_changed_at = $2,
    updated_at = now()
WHERE clearance_id = $1
"""

_UPDATE_UNDER_REVIEW_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'UnderReview',
    last_status_changed_at = $2,
    updated_at = now()
WHERE clearance_id = $1
"""

_UPDATE_APPROVED_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'Approved',
    last_status_changed_at = $2,
    last_reviewed_by_actor_id = $3,
    valid_from = COALESCE($4, valid_from),
    valid_until = COALESCE($5, valid_until),
    updated_at = now()
WHERE clearance_id = $1
"""

_UPDATE_REJECTED_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'Rejected',
    last_status_changed_at = $2,
    last_status_reason = $3,
    last_reviewed_by_actor_id = $4,
    updated_at = now()
WHERE clearance_id = $1
"""

_UPDATE_ACTIVATED_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'Active',
    last_status_changed_at = $2,
    updated_at = now()
WHERE clearance_id = $1
"""

_UPDATE_EXPIRED_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'Expired',
    last_status_changed_at = $2,
    last_status_reason = $3,
    updated_at = now()
WHERE clearance_id = $1
"""

_UPDATE_SUPERSEDED_SQL = """
UPDATE proj_safety_clearance_summary
SET status = 'Superseded',
    last_status_changed_at = $2,
    updated_at = now()
WHERE clearance_id = $1
"""


def split_binding_ids(
    bindings: list[dict[str, Any]],
) -> tuple[list[UUID], list[UUID], list[UUID], list[UUID]]:
    """Pivot the polymorphic bindings list into 4 typed UUID arrays.

    ExternalBinding entries are skipped per the migration comment: not
    projected today; consumers needing them fetch the aggregate via
    `get_clearance` or wait for the future binding-projection split.
    """
    subject_ids: list[UUID] = []
    asset_ids: list[UUID] = []
    run_ids: list[UUID] = []
    procedure_ids: list[UUID] = []
    for b in bindings:
        kind = b.get("kind")
        if kind == "Subject":
            subject_ids.append(UUID(b["id"]))
        elif kind == "Asset":
            asset_ids.append(UUID(b["id"]))
        elif kind == "Run":
            run_ids.append(UUID(b["id"]))
        elif kind == "Procedure":
            procedure_ids.append(UUID(b["id"]))
        # External: skipped (anti-corruption refs, not projected)
    return subject_ids, asset_ids, run_ids, procedure_ids


class ClearanceSummaryProjection:
    """Maintains the `proj_safety_clearance_summary` read model."""

    name = "proj_safety_clearance_summary"
    subscribed_event_types = frozenset(
        {
            "ClearanceRegistered",
            "ClearanceSubmitted",
            "ClearanceReviewStarted",
            "ClearanceReviewStepAppended",
            "ClearanceApproved",
            "ClearanceRejected",
            "ClearanceActivated",
            "ClearanceExpired",
            "ClearanceSuperseded",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "ClearanceRegistered":
            payload = event.payload
            subject_ids, asset_ids, run_ids, procedure_ids = split_binding_ids(
                payload.get("bindings", [])
            )
            raw_valid_from = payload.get("valid_from")
            raw_valid_until = payload.get("valid_until")
            raw_parent = payload.get("parent_clearance_id")
            await conn.execute(
                _INSERT_CLEARANCE_SQL,
                UUID(payload["clearance_id"]),
                payload["kind"],
                UUID(payload["facility_asset_id"]),
                payload["title"],
                payload.get("external_id"),
                payload.get("risk_band"),
                subject_ids,
                asset_ids,
                run_ids,
                procedure_ids,
                UUID(raw_parent) if raw_parent is not None else None,
                datetime.fromisoformat(payload["occurred_at"]),
                datetime.fromisoformat(raw_valid_from) if raw_valid_from is not None else None,
                datetime.fromisoformat(raw_valid_until) if raw_valid_until is not None else None,
            )
            return

        if event.event_type == "ClearanceSubmitted":
            await conn.execute(
                _UPDATE_SUBMITTED_SQL,
                UUID(event.payload["clearance_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ClearanceReviewStarted":
            await conn.execute(
                _UPDATE_UNDER_REVIEW_SQL,
                UUID(event.payload["clearance_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ClearanceApproved":
            payload = event.payload
            raw_valid_from = payload.get("valid_from")
            raw_valid_until = payload.get("valid_until")
            await conn.execute(
                _UPDATE_APPROVED_SQL,
                UUID(payload["clearance_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
                event.principal_id,
                datetime.fromisoformat(raw_valid_from) if raw_valid_from is not None else None,
                datetime.fromisoformat(raw_valid_until) if raw_valid_until is not None else None,
            )
            return

        if event.event_type == "ClearanceRejected":
            payload = event.payload
            await conn.execute(
                _UPDATE_REJECTED_SQL,
                UUID(payload["clearance_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
                payload["reason"],
                event.principal_id,
            )
            return

        if event.event_type == "ClearanceActivated":
            await conn.execute(
                _UPDATE_ACTIVATED_SQL,
                UUID(event.payload["clearance_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ClearanceExpired":
            payload = event.payload
            await conn.execute(
                _UPDATE_EXPIRED_SQL,
                UUID(payload["clearance_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
                payload["reason"],
            )
            return

        if event.event_type == "ClearanceSuperseded":
            # `by_clearance_id` is on the payload but not surfaced as a
            # projection column today; defer the parent->child denorm
            # until a list-view consumer asks for it (mirrors the
            # ExternalBinding-projection deferral pattern). The child's
            # `parent_clearance_id` already gives child->parent direction
            # via the existing projection column.
            await conn.execute(
                _UPDATE_SUPERSEDED_SQL,
                UUID(event.payload["clearance_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ClearanceReviewStepAppended":
            # No projection update: reviewer chain lives on aggregate stream
            # only. Subscribed-but-no-op keeps the worker's set complete
            # without denormalizing the chain.
            return

        # Unsubscribed event type (defensive; the worker shouldn't deliver
        # them given subscribed_event_types).
        return


__all__ = ["ClearanceSummaryProjection"]
