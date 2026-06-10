"""Data BC ports: cross-aggregate / cross-port surfaces consumed by Data slices.

`EditionSerializerPort` is the per-kind serializer surface invoked by
`seal_edition` + `publish_edition` to render an Edition as a citation
artifact (RO-Crate JSON-LD, DataCite XML, Croissant JSON, etc.).

`DistributionLookup` resolves the canonical `Distribution` row for a
given Dataset; consumed at `seal_edition` time to build the
serializer's `DatasetRef` boundary.
"""

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
    "CanonicalDistributionLookupResult",
    "DatasetRef",
    "DistributionLookup",
    "EditionSerializerPort",
    "SerializedEdition",
]
