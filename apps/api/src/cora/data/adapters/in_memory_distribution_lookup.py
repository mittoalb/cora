"""In-memory `DistributionLookup` adapter for unit + contract tests.

Tracks Distribution rows in a `dict[UUID, CanonicalDistributionLookupResult]`
keyed by `distribution_id`. `lookup_canonical_by_dataset` filters by
`dataset_id`, drops Discarded entries, and returns the result with
the smallest `distribution_id` (matches the production adapter's
`ORDER BY distribution_id LIMIT 1`).
"""

from threading import Lock
from uuid import UUID

from cora.data.aggregates.distribution.state import DistributionStatus
from cora.data.ports.distribution_lookup import CanonicalDistributionLookupResult


class InMemoryDistributionLookup:
    """Thread-safe in-memory implementation of the `DistributionLookup` port."""

    def __init__(self) -> None:
        self._records: dict[UUID, CanonicalDistributionLookupResult] = {}
        self._lock = Lock()

    def register(self, result: CanonicalDistributionLookupResult) -> None:
        """Test helper: install a Distribution lookup row."""
        with self._lock:
            self._records[result.distribution_id] = result

    async def lookup_canonical_by_dataset(
        self,
        dataset_id: UUID,
    ) -> CanonicalDistributionLookupResult | None:
        with self._lock:
            candidates = [
                record
                for record in self._records.values()
                if record.dataset_id == dataset_id
                and record.status is not DistributionStatus.DISCARDED
            ]
        if not candidates:
            return None
        return min(candidates, key=lambda record: record.distribution_id)


__all__ = ["InMemoryDistributionLookup"]
