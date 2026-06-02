"""AssetFamilyMembershipProjection: folds Asset<->Family membership
events into the `proj_equipment_asset_family_membership` read model.

Per-row noun is `membership`: each row records that a specific Asset
is a member of a specific Family classification. The set-theoretic
framing reads naturally in both directions: "Families this Asset
belongs to" (per-Asset by primary key) and "Assets belonging to this
Family" (per-Family via the secondary index that the next phase's
"list Assets affording requirement X" diagnostic will use).

Subscribed events:
  - AssetFamilyAdded   -> INSERT (asset_id, family_id, added_at)
                          with ON CONFLICT DO NOTHING for replay safety
  - AssetFamilyRemoved -> DELETE matching (asset_id, family_id)

The aggregate state (`Asset.family_ids`) is the canonical source; this
projection mirrors the relation for cross-aggregate query
convenience. Aggregate `Asset.family_ids` answers "Families of this
Asset"; this projection answers both that and the reverse.

Both event types are idempotent at the projection layer:
  - INSERT ... ON CONFLICT DO NOTHING tolerates duplicate Adds.
  - DELETE is naturally idempotent (DELETE of a non-existent row is
    a no-op).
The aggregate's decider already enforces strict-not-idempotent
semantics at command time (`AssetCannotAddFamilyError` on duplicate,
`AssetCannotRemoveFamilyError` on missing); the projection's
relaxed posture is the standard CORA pattern for replay safety.

Forward-compat: the next phase extends `inspect_plan_binding`'s
diagnostic with "other Assets affording missing requirement X." That
extension MUST source its candidate set from THIS projection (a
single SQL join against `proj_equipment_family_summary` for the
affordance filter), NOT per-Asset event-stream replay. The reverse
index `_by_family_idx` exists for exactly that query pattern.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_equipment_asset_family_membership
    (asset_id, family_id, added_at)
VALUES ($1, $2, $3)
ON CONFLICT (asset_id, family_id) DO NOTHING
"""

_DELETE_SQL = """
DELETE FROM proj_equipment_asset_family_membership
WHERE asset_id = $1 AND family_id = $2
"""


class AssetFamilyMembershipProjection:
    """Maintains the `proj_equipment_asset_family_membership` join read model."""

    name = "proj_equipment_asset_family_membership"
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


__all__ = ["AssetFamilyMembershipProjection"]
