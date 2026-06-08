"""FacilitySummaryProjection: folds the Facility aggregate's events into
the `proj_federation_facility_summary` read model.

Subscribed events:
  - FacilityRegistered                       -> INSERT
                                                (status='Active',
                                                 registered_at=occurred_at)
  - FacilityDecommissioned                   -> UPDATE
                                                status='Decommissioned',
                                                decommissioned_at=occurred_at,
                                                decommissioned_by
  - FacilityTrustAnchorCredentialAdded       -> UPDATE append
                                                credential_id into
                                                trust_anchor_credential_ids
                                                JSONB array, de-duplicated +
                                                sorted
  - FacilityTrustAnchorCredentialRemoved     -> UPDATE remove
                                                credential_id from
                                                trust_anchor_credential_ids
                                                JSONB array

## Code uniqueness

`code` is UNIQUE across the table (no partial WHERE clause; covers
Active AND Decommissioned rows) per [[project_facility_aggregate_design]]
L2 two-layer code-uniqueness lock. Decommissioned facilities' codes
stay reserved and cannot be reused for a new Active row.

The live-path uniqueness check happens upstream via the deterministic
`facility_stream_id` derivation + `append(expected_version=0)`
ConcurrencyError translation; this projection UNIQUE INDEX is
defense-in-depth against projection-rebuild drift and out-of-band SQL.

## Alternate identifiers + trust anchors

`alternate_identifiers` (PIDINST Property 13) lands as a JSONB array on
genesis. `trust_anchor_credential_ids` ships as an empty JSONB array on
genesis; populated by Slice 6 Sub-Slice B's add / remove transitions
(this module). Sub-Slice C will gate Seal initialize / rotate on
set-membership against this column.

`persistent_id` (PIDINST Property 1) is reserved as a nullable JSONB
column for the future `assign_facility_persistent_id` slice.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_FACILITY_SQL = """
INSERT INTO proj_federation_facility_summary
    (facility_id, code, display_name, kind, parent_id,
     status, alternate_identifiers, trust_anchor_credential_ids,
     persistent_id, registered_at, registered_by)
VALUES ($1, $2, $3, $4, $5,
        'Active', $6, '[]'::jsonb,
        NULL, $7, $8)
ON CONFLICT (facility_id) DO NOTHING
"""

_UPDATE_DECOMMISSIONED_SQL = """
UPDATE proj_federation_facility_summary
SET status = 'Decommissioned',
    decommissioned_at = $2,
    decommissioned_by = $3,
    updated_at = now()
WHERE facility_id = $1
"""

# Append credential_id text into trust_anchor_credential_ids JSONB array,
# deduplicated and sorted. Mirrors the asset.alternate_identifiers
# precedent with single-key elements (UUID-as-text strings) rather than
# the (kind, value) pair shape.
_UPDATE_TRUST_ANCHOR_ADDED_SQL = """
UPDATE proj_federation_facility_summary
SET trust_anchor_credential_ids = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem)
            FROM (
                SELECT DISTINCT elem
                FROM jsonb_array_elements_text(
                    trust_anchor_credential_ids || jsonb_build_array($2::text)
                ) AS elem
                ORDER BY elem
            ) AS dedup
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE facility_id = $1
"""

# Filter-out the matching credential_id element. Empty result collapses
# to `[]` via COALESCE so the NOT NULL constraint holds.
_UPDATE_TRUST_ANCHOR_REMOVED_SQL = """
UPDATE proj_federation_facility_summary
SET trust_anchor_credential_ids = COALESCE(
        (
            SELECT jsonb_agg(elem ORDER BY elem)
            FROM jsonb_array_elements_text(trust_anchor_credential_ids) AS elem
            WHERE elem != $2::text
        ),
        '[]'::jsonb
    ),
    updated_at = now()
WHERE facility_id = $1
"""


class FacilitySummaryProjection:
    """Maintains the `proj_federation_facility_summary` read model."""

    name = "proj_federation_facility_summary"
    subscribed_event_types = frozenset(
        {
            "FacilityRegistered",
            "FacilityDecommissioned",
            "FacilityTrustAnchorCredentialAdded",
            "FacilityTrustAnchorCredentialRemoved",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "FacilityRegistered":
            payload = event.payload
            raw_parent = payload.get("parent_id")
            registered_at = datetime.fromisoformat(payload["occurred_at"])
            # SAVEPOINT-wrap: the (code) UNIQUE constraint is a defense-
            # in-depth cross-stream invariant; collisions surface as
            # IntegrityError on contaminated streams.
            async with conn.transaction():
                await conn.execute(
                    _INSERT_FACILITY_SQL,
                    UUID(payload["facility_id"]),
                    payload["code"],
                    payload["display_name"],
                    payload["kind"],
                    UUID(raw_parent) if raw_parent is not None else None,
                    payload.get("alternate_identifiers", []),
                    registered_at,
                    UUID(payload["registered_by"]),
                )
            return

        if event.event_type == "FacilityDecommissioned":
            payload = event.payload
            await conn.execute(
                _UPDATE_DECOMMISSIONED_SQL,
                UUID(payload["facility_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
                UUID(payload["decommissioned_by"]),
            )
            return

        if event.event_type == "FacilityTrustAnchorCredentialAdded":
            payload = event.payload
            await conn.execute(
                _UPDATE_TRUST_ANCHOR_ADDED_SQL,
                UUID(payload["facility_id"]),
                payload["credential_id"],
            )
            return

        if event.event_type == "FacilityTrustAnchorCredentialRemoved":
            payload = event.payload
            await conn.execute(
                _UPDATE_TRUST_ANCHOR_REMOVED_SQL,
                UUID(payload["facility_id"]),
                payload["credential_id"],
            )
            return

        return


__all__ = ["FacilitySummaryProjection"]
