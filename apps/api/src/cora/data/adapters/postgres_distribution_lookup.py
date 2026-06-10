"""Postgres-backed `DistributionLookup` adapter for production wiring.

Queries `proj_data_distribution_summary` for the canonical (lowest-id,
non-Discarded) Distribution row for a given Dataset. Constructs the
typed `DistributionUri` / `DatasetChecksum` / `DatasetEncoding` value
objects from the projection's raw columns at the return boundary.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownArgumentType=false

import json
from typing import Any
from uuid import UUID

import asyncpg

from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.distribution.state import (
    DistributionStatus,
    DistributionUri,
)
from cora.data.ports.distribution_lookup import CanonicalDistributionLookupResult

_LOOKUP_SQL = """
SELECT distribution_id, dataset_id, uri, checksum, byte_size, encoding, status
FROM proj_data_distribution_summary
WHERE dataset_id = $1
  AND status != 'Discarded'
ORDER BY distribution_id
LIMIT 1
"""


def _parse_jsonb(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


class PostgresDistributionLookup:
    """Reads `proj_data_distribution_summary` for canonical Distribution rows."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup_canonical_by_dataset(
        self,
        dataset_id: UUID,
    ) -> CanonicalDistributionLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, dataset_id)
        if row is None:
            return None
        checksum_obj = _parse_jsonb(row["checksum"])
        encoding_obj = _parse_jsonb(row["encoding"])
        return CanonicalDistributionLookupResult(
            distribution_id=row["distribution_id"],
            dataset_id=row["dataset_id"],
            uri=DistributionUri(row["uri"]),
            checksum=DatasetChecksum(
                algorithm=checksum_obj["algorithm"],
                value=checksum_obj["value"],
            ),
            byte_size=int(row["byte_size"]),
            encoding=DatasetEncoding(
                media_type=encoding_obj["media_type"],
                conforms_to=frozenset(encoding_obj.get("conforms_to", [])),
            ),
            status=DistributionStatus(row["status"]),
        )


__all__ = ["PostgresDistributionLookup"]
