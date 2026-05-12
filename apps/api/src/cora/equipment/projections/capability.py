"""CapabilitySummaryProjection: folds the Capability aggregate's
3 lifecycle events into the `proj_equipment_capability_summary`
read model that backs `GET /capabilities`.

Subscribed events:
  - CapabilityDefined   -> INSERT (status=Defined, version_tag=NULL)
  - CapabilityVersioned -> UPDATE status=Versioned + version_tag from payload
  - CapabilityDeprecated -> UPDATE status=Deprecated (version_tag preserved
                            on purpose; the audit trail of "last
                            revised at version X before deprecation"
                            stays visible)

All branches idempotent. `version_tag` lands in the projection ONLY
on CapabilityVersioned; the Defined INSERT leaves it NULL and the
Deprecated UPDATE doesn't touch it.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CAPABILITY_SQL = """
INSERT INTO proj_equipment_capability_summary
    (capability_id, name, status, version_tag, created_at)
VALUES ($1, $2, 'Defined', NULL, $3)
ON CONFLICT (capability_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_capability_summary
SET status = 'Versioned', version_tag = $2, updated_at = now()
WHERE capability_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_equipment_capability_summary
SET status = 'Deprecated', updated_at = now()
WHERE capability_id = $1
"""


class CapabilitySummaryProjection:
    """Maintains the `proj_equipment_capability_summary` read model."""

    name = "proj_equipment_capability_summary"
    subscribed_event_types = frozenset(
        {"CapabilityDefined", "CapabilityVersioned", "CapabilityDeprecated"}
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "CapabilityDefined":
                await conn.execute(
                    _INSERT_CAPABILITY_SQL,
                    UUID(event.payload["capability_id"]),
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "CapabilityVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["capability_id"]),
                    event.payload["version_tag"],
                )
            case "CapabilityDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["capability_id"]),
                )
            case _:
                pass


__all__ = ["CapabilitySummaryProjection"]
