"""PermitSummaryProjection: folds the Permit aggregate's events into
the `proj_federation_permit_summary` read model that backs the
Permit list / get slices.

Subscribed events:
  - PermitDefined    -> INSERT (status='Defined', defined_at=occurred_at)
  - PermitActivated  -> UPDATE status='Active',    activated_at=occurred_at
  - PermitSuspended  -> UPDATE status='Suspended', suspended_at=occurred_at
  - PermitResumed    -> UPDATE status='Active',    resumed_at=occurred_at
  - PermitRevoked    -> UPDATE status='Revoked',   revoked_at=occurred_at

## Polymorphic terms (tagged union)

`terms` on `PermitDefined` is the tagged dict
`{"kind": "Outbound" | "Inbound", ...}` (per the aggregate's
`serialize_terms`). The projection writes the discriminator into the
`terms_kind` column verbatim (PascalCase `'Outbound' | 'Inbound'`
matching the Direction StrEnum), splits the per-direction fields
into their respective columns, and leaves the opposite-arc columns
NULL. The DB-level exclusive-arc CHECK constraint enforces the
invariant.

## Path C lifecycle timestamps

Genesis timestamp `defined_at` comes from the `PermitDefined` event's
envelope `occurred_at`; transition timestamps are filled by the
matching transition events.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_PERMIT_SQL = """
INSERT INTO proj_federation_permit_summary
    (permit_id, peer_facility_id, direction,
     allowed_credentials, allowed_payload_types, allowed_artifact_kinds,
     abi_tier_floor, expires_at, defined_by_actor_id, status, terms_kind,
     read_scope, onward_action_scope, scope_set,
     accepted_canonicalization_versions, required_receipt_kinds,
     publisher_grant_correlation_handle, inbound_allowed_artifact_kinds,
     defined_at)
VALUES ($1, $2, $3,
        $4::jsonb, $5::jsonb, $6::jsonb,
        $7, $8, $9, 'Defined', $10,
        $11::jsonb, $12::jsonb, $13::jsonb,
        $14::jsonb, $15::jsonb,
        $16, $17::jsonb,
        $18)
ON CONFLICT (permit_id) DO NOTHING
"""

_UPDATE_PERMIT_ACTIVATED_SQL = """
UPDATE proj_federation_permit_summary
SET status = 'Active',
    activated_at = $2,
    updated_at = now()
WHERE permit_id = $1
"""

_UPDATE_PERMIT_SUSPENDED_SQL = """
UPDATE proj_federation_permit_summary
SET status = 'Suspended',
    suspended_at = $2,
    updated_at = now()
WHERE permit_id = $1
"""

_UPDATE_PERMIT_RESUMED_SQL = """
UPDATE proj_federation_permit_summary
SET status = 'Active',
    resumed_at = $2,
    updated_at = now()
WHERE permit_id = $1
"""

_UPDATE_PERMIT_REVOKED_SQL = """
UPDATE proj_federation_permit_summary
SET status = 'Revoked',
    revoked_at = $2,
    updated_at = now()
WHERE permit_id = $1
"""


def _split_terms(terms: dict[str, Any]) -> dict[str, Any]:
    """Split the tagged terms dict into per-column JSON values.

    Returns a flat dict keyed by the projection column names. The
    opposite-arc columns are set to None so the per-direction exclusive
    arc CHECK constraint is satisfied.
    """
    kind = terms.get("kind")
    if kind == "Outbound":
        return {
            "terms_kind": "Outbound",
            "read_scope": json.dumps(terms["read_scope"]),
            "onward_action_scope": json.dumps(terms["onward_action_scope"]),
            "scope_set": json.dumps(terms["scope_set"]),
            "accepted_canonicalization_versions": None,
            "required_receipt_kinds": None,
            "publisher_grant_correlation_handle": None,
            "inbound_allowed_artifact_kinds": None,
        }
    if kind == "Inbound":
        return {
            "terms_kind": "Inbound",
            "read_scope": None,
            "onward_action_scope": None,
            "scope_set": None,
            "accepted_canonicalization_versions": json.dumps(
                terms["accepted_canonicalization_versions"]
            ),
            "required_receipt_kinds": json.dumps(terms["required_receipt_kinds"]),
            "publisher_grant_correlation_handle": terms.get("publisher_grant_correlation_handle"),
            "inbound_allowed_artifact_kinds": json.dumps(terms["inbound_allowed_artifact_kinds"]),
        }
    msg = f"Unknown Permit terms kind discriminator in payload: {kind!r}"
    raise ValueError(msg)


class PermitSummaryProjection:
    """Maintains the `proj_federation_permit_summary` read model."""

    name = "proj_federation_permit_summary"
    subscribed_event_types = frozenset(
        {
            "PermitDefined",
            "PermitActivated",
            "PermitSuspended",
            "PermitResumed",
            "PermitRevoked",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "PermitDefined":
            payload = event.payload
            terms_cols = _split_terms(payload["terms"])
            defined_at = datetime.fromisoformat(payload["occurred_at"])
            # SAVEPOINT-wrap the INSERT: the CHECK-driven failure modes
            # (terms_kind mismatch, exclusive arc violation) are
            # contaminated-payload symptoms that should not poison the
            # bookmark transaction.
            async with conn.transaction():
                await conn.execute(
                    _INSERT_PERMIT_SQL,
                    UUID(payload["permit_id"]),
                    payload["peer_facility_id"],
                    payload["direction"],
                    json.dumps(payload["allowed_credentials"]),
                    json.dumps(payload["allowed_payload_types"]),
                    json.dumps(payload["allowed_artifact_kinds"]),
                    payload["abi_tier_floor"],
                    datetime.fromisoformat(payload["expires_at"]),
                    UUID(payload["defined_by_actor_id"]),
                    terms_cols["terms_kind"],
                    terms_cols["read_scope"],
                    terms_cols["onward_action_scope"],
                    terms_cols["scope_set"],
                    terms_cols["accepted_canonicalization_versions"],
                    terms_cols["required_receipt_kinds"],
                    terms_cols["publisher_grant_correlation_handle"],
                    terms_cols["inbound_allowed_artifact_kinds"],
                    defined_at,
                )
            return

        if event.event_type == "PermitActivated":
            payload = event.payload
            await conn.execute(
                _UPDATE_PERMIT_ACTIVATED_SQL,
                UUID(payload["permit_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        if event.event_type == "PermitSuspended":
            payload = event.payload
            await conn.execute(
                _UPDATE_PERMIT_SUSPENDED_SQL,
                UUID(payload["permit_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        if event.event_type == "PermitResumed":
            payload = event.payload
            await conn.execute(
                _UPDATE_PERMIT_RESUMED_SQL,
                UUID(payload["permit_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        if event.event_type == "PermitRevoked":
            payload = event.payload
            await conn.execute(
                _UPDATE_PERMIT_REVOKED_SQL,
                UUID(payload["permit_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        return


__all__ = ["PermitSummaryProjection"]
