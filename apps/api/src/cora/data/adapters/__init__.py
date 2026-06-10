"""Data BC adapters: concrete implementations of Data ports.

`RoCrate12Adapter`: implements `EditionSerializerPort` for
`EditionKind.ROCRATE` producing JSON-LD per the RO-Crate 1.2 +
Workflow Run Crate profiles.

`PostgresDistributionLookup` + `InMemoryDistributionLookup`:
`DistributionLookup` adapters reading `proj_data_distribution_summary`
or an in-process dict for the canonical Distribution row per Dataset.

Test-only stub adapters live alongside the production adapters for
reuse across unit + contract + integration tests:

  - `StubEditionSerializer`: returns a pre-configured `SerializedEdition`
  - `FailingEditionSerializer`: raises a pre-configured exception
  - `PerKindEditionSerializer`: dispatches to per-kind serializers
"""

from cora.data.adapters.in_memory_distribution_lookup import (
    InMemoryDistributionLookup,
)
from cora.data.adapters.postgres_distribution_lookup import (
    PostgresDistributionLookup,
)
from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.adapters.stub_edition_serializer import (
    FailingEditionSerializer,
    PerKindEditionSerializer,
    StubEditionSerializer,
)

__all__ = [
    "FailingEditionSerializer",
    "InMemoryDistributionLookup",
    "PerKindEditionSerializer",
    "PostgresDistributionLookup",
    "RoCrate12Adapter",
    "StubEditionSerializer",
]
