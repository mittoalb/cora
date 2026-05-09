"""Postgres-backed `IdempotencyStore` adapter.

`(principal_id, key)` is the composite primary key of the
`idempotency_keys` table; first-writer-wins is enforced via
`INSERT ... ON CONFLICT DO NOTHING` (race-safe under concurrent writes
without application-level locks).

Cached results are stored in a `result jsonb` column. The aggregate
JSON codec registered on the pool (see `postgres/pool.py`) round-trips
dicts and primitives transparently.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID

import asyncpg

from cora.infrastructure.ports.idempotency import CachedResult

_GET_SQL = """
SELECT command_hash, command_name, result
FROM idempotency_keys
WHERE principal_id = $1 AND key = $2
"""

_PUT_SQL = """
INSERT INTO idempotency_keys (principal_id, key, command_hash, command_name, result)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (principal_id, key) DO NOTHING
"""


class PostgresIdempotencyStore:
    """asyncpg-backed `IdempotencyStore` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, principal_id: UUID, key: str) -> CachedResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_GET_SQL, principal_id, key)
        if row is None:
            return None
        # asyncpg JSON codec (registered on the pool) deserializes jsonb
        # to Python objects; row["result"] is already dict / str / etc.
        return CachedResult(
            command_hash=str(row["command_hash"]),
            command_name=str(row["command_name"]),
            result=row["result"],
        )

    async def put(
        self,
        principal_id: UUID,
        key: str,
        record: CachedResult,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                _PUT_SQL,
                principal_id,
                key,
                record.command_hash,
                record.command_name,
                record.result,
            )
