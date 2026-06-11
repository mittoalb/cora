"""AttestationSummaryProjection: folds the Attestation aggregate's
single AttestationRecorded event into the
``proj_data_attestation_summary`` read model.

Subscribed events:
  - AttestationRecorded -> INSERT (always; terminal-at-genesis)

## ON CONFLICT semantics

Genesis INSERT uses ``ON CONFLICT (attestation_id) DO NOTHING`` for
stream-id idempotency (same precedent as DatasetSummaryProjection /
DistributionSummaryProjection). The Attestation stream id is the
attestation_id itself (no uuid5 derivation per L19), so a same-stream
collision is the only path; no cross-stream UNIQUE INDEX exists on
this table by design (per L14 strict-not-idempotent + the fact-chain
semantic that multiple Attestations for one tuple are first-class).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ATTESTATION_SQL = """
INSERT INTO proj_data_attestation_summary
    (attestation_id, dataset_id, distribution_id, kind, outcome,
     evidence, attested_at, attested_by)
VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
ON CONFLICT (attestation_id) DO NOTHING
"""


class AttestationSummaryProjection:
    """Maintains the ``proj_data_attestation_summary`` read model."""

    name = "proj_data_attestation_summary"
    subscribed_event_types = frozenset({"AttestationRecorded"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "AttestationRecorded":
                payload = event.payload
                attestation_id = UUID(payload["attestation_id"])
                dataset_id = UUID(payload["dataset_id"])
                raw_distribution = payload["distribution_id"]
                distribution_id = UUID(raw_distribution) if raw_distribution is not None else None
                kind = payload["kind"]
                outcome = payload["outcome"]
                evidence_json = json.dumps(payload["evidence"])
                attested_at = datetime.fromisoformat(payload["occurred_at"])
                attested_by = UUID(payload["attested_by"])
                await conn.execute(
                    _INSERT_ATTESTATION_SQL,
                    attestation_id,
                    dataset_id,
                    distribution_id,
                    kind,
                    outcome,
                    evidence_json,
                    attested_at,
                    attested_by,
                )
            case _:
                pass


__all__ = ["AttestationSummaryProjection"]
