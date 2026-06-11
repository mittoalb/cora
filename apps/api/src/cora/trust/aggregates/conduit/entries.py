"""Verdict entry: per-decision authz audit (verdict) row.

The first concrete entry type. Every call to the `Authorize` port
that this Conduit governs produces one `Verdict` entry row,
persisted to the `entries_conduit_verdicts` table.

This is the first instance of the **per-category writer pattern**
locked at gate-review L8: each entry kind has its own typed
dataclass + per-category Postgres adapter living alongside the
owning aggregate, with a category-local `VerdictStore` Protocol
(NOT a shared cross-BC port). Future kinds follow the same shape
(`<owning_bc>/aggregates/<agg>/entries.py`).

## Why this lives here, not in `cora.infrastructure.postgres`

The dataclass + Protocol describe Trust BC's domain shape — actor /
command / decision / reason are domain vocabulary, not infrastructure
primitives. The Postgres adapter that knows the SQL also lives here
because the SQL knows the column shape; splitting them across infra
and domain modules would require either a generic SQL builder or
duplicate column lists. Same trade-off the existing `events.py` per-
aggregate modules made (each owns its `to_payload` / `from_stored`).

## Why writes batch from day one

`append(rows: list[Verdict])` always takes a list, even for
the realistic "one decision at a time" case (single-element list).
When higher-cardinality entry categories ship (Observation in Run BC,
Activity in Operation BC), the shape is unchanged. Locked at
gate-review G4. Empty lists are a no-op.

## Why no read shape today

The `range` query for retrieval lands when a real consumer asks for
it (gate-review G2 deferral). Today the table is write-only from the
application's perspective; ad-hoc SQL covers any operator queries.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter class. The dataclass + Protocol stay strictly typed for
# every caller above the boundary.

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

VerdictDecision = Literal["Allow", "Deny"]


@dataclass(frozen=True)
class Verdict:
    """One row in the per-Conduit authz verdict logbook.

    `event_id` is the producer-assigned UUIDv7 identity (matches the
    existing event-sourcing convention). Used as the dedup key under
    at-least-once delivery; UNIQUE constraint enforced at the table
    level. `correlation_id` and `causation_id` thread through from
    the originating command's envelope for full audit traceability
    (gate-review G7 lock).
    """

    event_id: UUID
    conduit_id: UUID
    logbook_id: UUID
    actor_id: UUID
    command_name: str
    decision: VerdictDecision
    reason: str | None
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime


class VerdictStore(Protocol):
    """Per-category port for Verdict entry writes.

    Every Authorize port adapter that wants to emit verdict entries
    (TrustAuthorize today; future authz adapters similarly) takes a
    `VerdictStore` and calls `append(...)` per decision.

    Two implementations: `PostgresVerdictStore` (production) and
    `InMemoryVerdictStore` (tests / `app_env=test`). Both honor
    the same at-least-once contract: callers may retry the same
    `event_id`, the store dedups via the table's PK constraint
    (Postgres) or the in-memory dict (InMemory).
    """

    async def append(self, rows: list[Verdict]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_conduit_verdicts (
    event_id, conduit_id, logbook_id, actor_id, command_name,
    decision, reason, correlation_id, causation_id, occurred_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresVerdictStore:
    """asyncpg-backed `VerdictStore` implementation.

    Uses `ON CONFLICT (event_id) DO NOTHING` for idempotent retries:
    a producer that re-issues the same `event_id` (after a transient
    network failure on the previous attempt) is a no-op rather than
    a constraint violation. This matches the existing event-store
    UNIQUE-on-event_id pattern.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[Verdict]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        row.event_id,
                        row.conduit_id,
                        row.logbook_id,
                        row.actor_id,
                        row.command_name,
                        row.decision,
                        row.reason,
                        row.correlation_id,
                        row.causation_id,
                        row.occurred_at,
                    )
                    for row in rows
                ],
            )


class InMemoryVerdictStore:
    """Test / `app_env=test` adapter for `VerdictStore`.

    Dict keyed by `event_id` for trivial dedup. Exposes `all()` so
    contract / unit tests can assert what was emitted without going
    through Postgres.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, Verdict] = {}

    async def append(self, rows: list[Verdict]) -> None:
        for row in rows:
            # ON CONFLICT DO NOTHING semantics: existing wins (matches
            # the Postgres adapter's behavior under retry).
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[Verdict]:
        return list(self._rows.values())


__all__ = [
    "InMemoryVerdictStore",
    "PostgresVerdictStore",
    "Verdict",
    "VerdictDecision",
    "VerdictStore",
]
