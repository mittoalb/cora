"""AssetFamilyProjection: folds the Asset<->Family membership events
into the `proj_equipment_asset_families` read model.

Subscribed events:
  - AssetFamilyAdded   -> INSERT (asset_id, family_id, added_at)
                          with ON CONFLICT DO NOTHING for replay safety
  - AssetFamilyRemoved -> DELETE matching (asset_id, family_id)

The aggregate state (`Asset.families`) is the canonical source; this
projection mirrors the membership relation for cross-aggregate query
convenience. The dominant per-Asset read ("which Families does this
Asset carry") uses the primary key (asset_id, family_id); the
reverse-direction read ("which Assets carry Family X") uses the
`_by_family_idx` secondary index added by the migration.

Both event types are idempotent at the projection layer:
  - INSERT ... ON CONFLICT DO NOTHING tolerates duplicate Adds.
  - DELETE is naturally idempotent (DELETE of a non-existent row is
    a no-op).
The aggregate's decider already enforces strict-not-idempotent
semantics at command time (`AssetCannotAddFamilyError` on duplicate,
`AssetCannotRemoveFamilyError` on missing); the projection's
relaxed posture is the standard CORA pattern for replay safety.

Hoist trigger: the `inspect_plan_binding` slice's future
"other Assets affording requirement X" diagnostic is the first
read consumer that needs the reverse index. The
`AssetSummaryProjection` docstring's TODO ("Belong in a future
`proj_equipment_asset_capabilities` projection") is closed by this
projection.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_equipment_asset_families
    (asset_id, family_id, added_at)
VALUES ($1, $2, $3)
ON CONFLICT (asset_id, family_id) DO NOTHING
"""

_DELETE_SQL = """
DELETE FROM proj_equipment_asset_families
WHERE asset_id = $1 AND family_id = $2
"""


class AssetFamilyProjection:
    """Maintains the `proj_equipment_asset_families` join read model."""

    name = "proj_equipment_asset_families"
    subscribed_event_types = frozenset(
        {
            "AssetFamilyAdded",
            "AssetFamilyRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        asset_id = UUID(str(event.payload["asset_id"]))
        family_id = UUID(str(event.payload["family_id"]))
        match event.event_type:
            case "AssetFamilyAdded":
                await conn.execute(
                    _INSERT_SQL,
                    asset_id,
                    family_id,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AssetFamilyRemoved":
                await conn.execute(_DELETE_SQL, asset_id, family_id)
            case _:
                pass


__all__ = ["AssetFamilyProjection"]
