"""Data BC ports: cross-aggregate / cross-port surfaces consumed by Data slices.

`EditionSerializerPort` is the per-kind serializer surface invoked by
`seal_edition` + `publish_edition` to render an Edition as a citation
artifact (RO-Crate JSON-LD, DataCite XML, Croissant JSON, etc.).

`DistributionLookup` resolves the canonical `Distribution` row for a
given Dataset; consumed at `seal_edition` time to build the
serializer's `DatasetRef` boundary.

Per-BC port modules live here when the port is consumed only by Data
BC code paths (today also: ``ChecksumVerifierPort``). Cross-BC ports
(used by multiple BCs) live at ``cora.infrastructure.ports`` per
[[project_data_distribution_design]] L13 + W13.
"""

from cora.data.ports.checksum_verifier import (
    AlwaysMatchingChecksumVerifier,
    AlwaysMismatchingChecksumVerifier,
    AlwaysUnreachableChecksumVerifier,
    ChecksumVerificationResult,
    ChecksumVerifierPort,
    ChecksumVerifierUnsupportedSchemeError,
    ConfiguredChecksumVerifier,
    Match,
    Mismatch,
    Unreachable,
)
from cora.data.ports.distribution_lookup import (
    CanonicalDistributionLookupResult,
    DistributionLookup,
)
from cora.data.ports.edition_serializer import (
    DatasetRef,
    EditionSerializerPort,
    SerializedEdition,
)

__all__ = [
    "AlwaysMatchingChecksumVerifier",
    "AlwaysMismatchingChecksumVerifier",
    "AlwaysUnreachableChecksumVerifier",
    "CanonicalDistributionLookupResult",
    "ChecksumVerificationResult",
    "ChecksumVerifierPort",
    "ChecksumVerifierUnsupportedSchemeError",
    "ConfiguredChecksumVerifier",
    "DatasetRef",
    "DistributionLookup",
    "EditionSerializerPort",
    "Match",
    "Mismatch",
    "SerializedEdition",
    "Unreachable",
]
