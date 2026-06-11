"""Cross-aggregate context the ``record_attestation`` decider validates against.

``AttestationRecordingContext`` is built by the ``record_attestation``
handler from ``load_dataset`` (always) and ``load_distribution`` (when
``command.distribution_id`` is set) calls before reaching the pure
decider. Per [[project_data_attestation_design]] L15 + L17 the handler
pre-loads both refs; the decider treats them as injected
proof-of-existence + carries the loaded peers in so the dual-binding
dataset_id-equality guard and the belt-and-braces checksum-equality
guard are O(1) closures over already-fetched data.

Slice-local module by design: only ``record_attestation`` uses it
today.

## Field semantics

  - ``dataset``: the parent Dataset (always required). The handler
    raises ``DatasetNotFoundError`` upstream if ``command.dataset_id``
    does not resolve, so the decider can assume this field is
    non-None.
  - ``distribution``: the bound Distribution (None when
    ``command.distribution_id`` is None for ConformsToValidated; the
    handler raises ``AttestationDistributionNotFoundError`` if a
    non-None distribution_id does not resolve). Used by the decider
    for the dataset_id-equality guard and the belt-and-braces
    checksum-equality guard.
"""

from dataclasses import dataclass

from cora.data.aggregates.dataset import Dataset
from cora.data.aggregates.distribution import Distribution


@dataclass(frozen=True)
class AttestationRecordingContext:
    """Snapshot of cross-aggregate references at Attestation-recording time."""

    dataset: Dataset
    distribution: Distribution | None
