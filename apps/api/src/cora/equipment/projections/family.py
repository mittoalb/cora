"""FamilySummaryProjection: folds the Family aggregate's
4 events into the `proj_equipment_family_summary` read model
that backs `GET /families`.

Subscribed events (BOTH new + legacy names per Marten/Axon dual-match
contract — the aggregate was renamed `Capability` → `Family`, but
legacy `Capability*` events stay in the log forever; the projection
must subscribe to both so a replay-from-zero on a deployment with
historical data produces a correct summary table. The apply path
reads `family_id` from new payloads and `capability_id` from legacy
payloads. See [[project_family_affordance_design]] "Locks" section
+ [[project_capability_research]] dual-match anti-hooks.):

  - FamilyDefined / CapabilityDefined        -> INSERT
        (status=Defined, version_tag=NULL,
         settings_schema_present=FALSE)
  - FamilyVersioned / CapabilityVersioned    -> UPDATE
        status=Versioned + version_tag from payload
  - FamilyDeprecated / CapabilityDeprecated  -> UPDATE
        status=Deprecated (version_tag preserved on purpose; the
        audit trail of "last revised at version X before
        deprecation" stays visible)
  - FamilySettingsSchemaUpdated /
    CapabilitySettingsSchemaUpdated          -> UPDATE
        settings_schema_present (TRUE if settings_schema is
        non-NULL; FALSE if cleared via NULL)

All branches idempotent. `version_tag` lands in the projection ONLY
on Versioned events; the Defined INSERT leaves it NULL and the
Deprecated UPDATE doesn't touch it. `settings_schema_present` is
TRUE iff the latest *SettingsSchemaUpdated payload's
`settings_schema` was non-NULL; the schema content itself lives in
the event stream (loaded on demand, not projected to keep the
summary table small).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_FAMILY_SQL = """
INSERT INTO proj_equipment_family_summary
    (family_id, name, status, version_tag, created_at,
     settings_schema_present)
VALUES ($1, $2, 'Defined', NULL, $3, FALSE)
ON CONFLICT (family_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_equipment_family_summary
SET status = 'Versioned',
    version_tag = $2,
    versioned_at = $3,
    updated_at = now()
WHERE family_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_equipment_family_summary
SET status = 'Deprecated',
    deprecated_at = $2,
    updated_at = now()
WHERE family_id = $1
"""

_UPDATE_SCHEMA_PRESENT_SQL = """
UPDATE proj_equipment_family_summary
SET settings_schema_present = $2, updated_at = now()
WHERE family_id = $1
"""


def _id(payload: dict[str, object]) -> UUID:
    """Read the aggregate id from either the new `family_id` payload
    key (post-5i) or the legacy `capability_id` key (pre-5i). Dual-
    key fallback mirrors the dual-match in `family/events.from_stored`.
    """
    raw = payload.get("family_id") or payload["capability_id"]
    return UUID(str(raw))


class FamilySummaryProjection:
    """Maintains the `proj_equipment_family_summary` read model."""

    name = "proj_equipment_family_summary"
    subscribed_event_types = frozenset(
        {
            # Current event type names (post-5i)
            "FamilyDefined",
            "FamilyVersioned",
            "FamilyDeprecated",
            "FamilySettingsSchemaUpdated",
            # Legacy event type names (pre-5i; stay forever per
            # Marten/Axon dual-match contract). Without these, a
            # projection replay on a deployment with historical data
            # would silently skip legacy events and produce an
            # incomplete summary table.
            "CapabilityDefined",
            "CapabilityVersioned",
            "CapabilityDeprecated",
            "CapabilitySettingsSchemaUpdated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "FamilyDefined" | "CapabilityDefined":
                await conn.execute(
                    _INSERT_FAMILY_SQL,
                    _id(event.payload),
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FamilyVersioned" | "CapabilityVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    _id(event.payload),
                    event.payload["version_tag"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FamilyDeprecated" | "CapabilityDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    _id(event.payload),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FamilySettingsSchemaUpdated" | "CapabilitySettingsSchemaUpdated":
                await conn.execute(
                    _UPDATE_SCHEMA_PRESENT_SQL,
                    _id(event.payload),
                    event.payload.get("settings_schema") is not None,
                )
            case _:
                pass


__all__ = ["FamilySummaryProjection"]
