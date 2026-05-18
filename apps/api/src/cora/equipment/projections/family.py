"""FamilySummaryProjection: folds the Family aggregate's
4 events into the `proj_equipment_family_summary` read model
that backs `GET /families`.

Subscribed events:
  - FamilyDefined        -> INSERT (status=Defined, version_tag=NULL,
                                        settings_schema_present=FALSE)
  - FamilyVersioned      -> UPDATE status=Versioned + version_tag
                                        from payload
  - FamilyDeprecated     -> UPDATE status=Deprecated (version_tag
                                        preserved on purpose; the audit
                                        trail of "last revised at
                                        version X before deprecation"
                                        stays visible)
  - FamilySettingsSchemaUpdated  -> UPDATE settings_schema_present (TRUE
                                        if settings_schema is non-NULL;
                                        FALSE if cleared via NULL)
                                        (Phase 5g-a)

All branches idempotent. `version_tag` lands in the projection ONLY
on FamilyVersioned; the Defined INSERT leaves it NULL and the
Deprecated UPDATE doesn't touch it. `settings_schema_present` is
TRUE iff the latest `FamilySettingsSchemaUpdated.settings_schema`
payload was non-NULL; the schema content itself lives in the event
stream (loaded on demand, not projected to keep the summary table
small).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CAPABILITY_SQL = """
INSERT INTO proj_equipment_family_summary
    (family_id, name, status, version_tag, created_at,
     settings_schema_present)
VALUES ($1, $2, 'Defined', NULL, $3, FALSE)
ON CONFLICT (family_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_family_summary
SET status = 'Versioned', version_tag = $2, updated_at = now()
WHERE family_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_equipment_family_summary
SET status = 'Deprecated', updated_at = now()
WHERE family_id = $1
"""

_UPDATE_SCHEMA_PRESENT_SQL = """
UPDATE proj_equipment_family_summary
SET settings_schema_present = $2, updated_at = now()
WHERE family_id = $1
"""


class FamilySummaryProjection:
    """Maintains the `proj_equipment_family_summary` read model."""

    name = "proj_equipment_family_summary"
    subscribed_event_types = frozenset(
        {
            "FamilyDefined",
            "FamilyVersioned",
            "FamilyDeprecated",
            "FamilySettingsSchemaUpdated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "FamilyDefined":
                await conn.execute(
                    _INSERT_CAPABILITY_SQL,
                    UUID(event.payload["family_id"]),
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FamilyVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["family_id"]),
                    event.payload["version_tag"],
                )
            case "FamilyDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["family_id"]),
                )
            case "FamilySettingsSchemaUpdated":
                await conn.execute(
                    _UPDATE_SCHEMA_PRESENT_SQL,
                    UUID(event.payload["family_id"]),
                    event.payload.get("settings_schema") is not None,
                )
            case _:
                pass


__all__ = ["FamilySummaryProjection"]
