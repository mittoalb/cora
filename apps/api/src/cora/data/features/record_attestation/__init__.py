"""Vertical slice for the ``RecordAttestation`` command.

Module-as-namespace surface mirrors ``register_distribution``:

    from cora.data.features import record_attestation

    cmd = record_attestation.RecordAttestation(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
        outcome="Match",
        evidence_expected_checksum="a" * 64,
        evidence_computed_checksum="a" * 64,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="HttpRangeChecksum",
        evidence_error_detail=None,
    )
    handler = record_attestation.bind(deps)
    attestation_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.record_attestation import tool
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.context import (
    AttestationRecordingContext,
)
from cora.data.features.record_attestation.decider import decide
from cora.data.features.record_attestation.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.data.features.record_attestation.route import router

__all__ = [
    "AttestationRecordingContext",
    "Handler",
    "IdempotentHandler",
    "RecordAttestation",
    "bind",
    "decide",
    "router",
    "tool",
]
