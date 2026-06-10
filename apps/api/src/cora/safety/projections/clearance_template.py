"""ClearanceTemplateSummaryProjection: folds the ClearanceTemplate aggregate's
events into the `proj_safety_clearance_template_summary` read model.

Subscribed events:
  - ClearanceTemplateDefined     -> INSERT (status=Draft)
  - ClearanceTemplateActivated   -> UPDATE status='Active'
  - ClearanceTemplateVersioned   -> UPDATE version + supersedes_template_id
  - ClearanceTemplateDeprecated  -> UPDATE status='Deprecated'
  - ClearanceTemplateWithdrawn   -> UPDATE status='Withdrawn'

Status values are hardcoded per event type, mirroring the evolver's per-arm
mapping per the ClearanceTemplateStatus enum.

All branches are idempotent. The ClearanceTemplateDefined INSERT uses
`ON CONFLICT (template_id) DO NOTHING` to handle duplicate-event replay.
Activated and Versioned UPDATEs are naturally idempotent (same status / same
version value re-applied).

The projection's PARTIAL UNIQUE INDEX on (facility_code, code) WHERE
status != 'Withdrawn' enforces facility-scoped uniqueness at the read side.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

_INSERT_CLEARANCE_TEMPLATE_SQL = """
INSERT INTO proj_safety_clearance_template_summary
    (template_id, facility_code, code, title, version, supersedes_template_id,
     external_ref, status, defined_at, defined_by, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, 'Draft', $8, $9, now(), now())
ON CONFLICT (template_id) DO NOTHING
"""

_UPDATE_CLEARANCE_TEMPLATE_STATUS_SQL = """
UPDATE proj_safety_clearance_template_summary
SET status = $2, updated_at = now()
WHERE template_id = $1
"""

_UPDATE_CLEARANCE_TEMPLATE_VERSION_SQL = """
UPDATE proj_safety_clearance_template_summary
SET version = $2, supersedes_template_id = $3, updated_at = now()
WHERE template_id = $1
"""


class ClearanceTemplateSummaryProjection:
    """Maintains the `proj_safety_clearance_template_summary` read model."""

    name = "proj_safety_clearance_template_summary"
    subscribed_event_types = frozenset(
        {
            "ClearanceTemplateDefined",
            "ClearanceTemplateActivated",
            "ClearanceTemplateVersioned",
            "ClearanceTemplateDeprecated",
            "ClearanceTemplateWithdrawn",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "ClearanceTemplateDefined":
            raw_supersedes = event.payload.get("supersedes_template_id")
            supersedes_template_id = UUID(raw_supersedes) if raw_supersedes is not None else None

            await conn.execute(
                _INSERT_CLEARANCE_TEMPLATE_SQL,
                UUID(event.payload["template_id"]),
                event.payload["facility_code"],
                event.payload["code"],
                event.payload["title"],
                event.payload.get("version", 1),
                supersedes_template_id,
                event.payload.get("external_ref"),
                datetime.fromisoformat(event.payload["occurred_at"]),
                UUID(event.payload["defined_by"]),
            )
            return

        if event.event_type == "ClearanceTemplateActivated":
            await conn.execute(
                _UPDATE_CLEARANCE_TEMPLATE_STATUS_SQL,
                UUID(event.payload["template_id"]),
                "Active",
            )
            return

        if event.event_type == "ClearanceTemplateVersioned":
            await conn.execute(
                _UPDATE_CLEARANCE_TEMPLATE_VERSION_SQL,
                UUID(event.payload["template_id"]),
                event.payload["new_version"],
                UUID(event.payload["supersedes_template_id"]),
            )
            return

        if event.event_type == "ClearanceTemplateDeprecated":
            await conn.execute(
                _UPDATE_CLEARANCE_TEMPLATE_STATUS_SQL,
                UUID(event.payload["template_id"]),
                "Deprecated",
            )
            return

        if event.event_type == "ClearanceTemplateWithdrawn":
            await conn.execute(
                _UPDATE_CLEARANCE_TEMPLATE_STATUS_SQL,
                UUID(event.payload["template_id"]),
                "Withdrawn",
            )
            return

        # Unsubscribed event types (defensive  --  the worker shouldn't
        # deliver them given subscribed_event_types, but the dispatch
        # is no-op-on-foreign-event-type as a safety net).
        return


__all__ = ["ClearanceTemplateSummaryProjection"]
