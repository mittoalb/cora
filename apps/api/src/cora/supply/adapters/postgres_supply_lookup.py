"""Postgres adapter implementing `SupplyLookup` over `proj_supply_summary`.

Consumed by Run BC's `start_run` handler and Operation BC's
`start_procedure` handler via the `Kernel.supply_lookup` port. Reads
the projection's `(supply_id, kind, scope, name, status)` columns;
returns Supplies grouped by kind, excluding `Decommissioned` rows.

## Why query the projection (not the event store)

Same rationale as `PostgresClearanceLookup`: cross-BC integration at
command time should go through a replicated read model, not a
synchronous call to the upstream aggregate. `proj_supply_summary` is
a denormalized cross-stream view maintained by the projection worker.
The lookup adapter reads it directly via the shared asyncpg pool.

## Query shape

Single SELECT with a single ANY() match over the indexed `kind`
column plus an explicit `Decommissioned` exclusion. The partial
UNIQUE INDEX on `(scope, kind, name)` already excludes
`Decommissioned` from uniqueness per
[[project_deregister_supply_design]]; this SELECT does the same
exclusion at the read side so tombstoned Supplies do not
contribute to gate satisfaction.

```sql
SELECT supply_id, kind, scope, name, status
FROM proj_supply_summary
WHERE kind = ANY($1) AND status != 'Decommissioned'
ORDER BY kind, registered_at, supply_id
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from typing import Any

import asyncpg

from cora.infrastructure.ports.supply_lookup import SupplyReference

_FIND_SUPPLIES_BY_KIND_SQL = """
SELECT supply_id, kind, scope, name, status
FROM proj_supply_summary
WHERE kind = ANY($1) AND status != 'Decommissioned'
ORDER BY kind, registered_at, supply_id
"""


class PostgresSupplyLookup:
    """asyncpg-backed `SupplyLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyReference]]:
        if not kinds:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FIND_SUPPLIES_BY_KIND_SQL,
                sorted(kinds),
            )
        grouped: dict[str, list[SupplyReference]] = {}
        for row in rows:
            ref = _row_to_reference(row)
            grouped.setdefault(ref.kind, []).append(ref)
        return grouped


def _row_to_reference(row: Any) -> SupplyReference:
    return SupplyReference(
        supply_id=str(row["supply_id"]),
        kind=str(row["kind"]),
        scope=str(row["scope"]),
        name=str(row["name"]),
        status=str(row["status"]),
    )
