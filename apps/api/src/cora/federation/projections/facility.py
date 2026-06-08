"""FacilitySummaryProjection: folds the Facility aggregate's events into
the `proj_federation_facility_summary` read model.

Subscribed events:
  - FacilityRegistered         -> INSERT (status='Active',
                                          registered_at=occurred_at)
  - FacilityDecommissioned     -> UPDATE status='Decommissioned',
                                         decommissioned_at=occurred_at,
                                         decommissioned_by

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
genesis. `trust_anchor_credential_ids` ships as an empty JSONB array
default; population is deferred to slice 6 binding when the
add/remove slices land.

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


class FacilitySummaryProjection:
    """Maintains the `proj_federation_facility_summary` read model."""

    name = "proj_federation_facility_summary"
    subscribed_event_types = frozenset(
        {
            "FacilityRegistered",
            "FacilityDecommissioned",
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

        return


__all__ = ["FacilitySummaryProjection"]
