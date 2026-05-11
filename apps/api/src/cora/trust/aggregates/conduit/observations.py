"""ConduitTraversal observation: per-decision authz audit row.

Phase 6f-5a's first concrete observation type. Every call to the
`Authorize` port that this Conduit governs produces one
`ConduitTraversal` observation row, persisted to the
`observations_conduit_traversals` table (defined in Atlas migration
`20260511130000`).

This is the first instance of the **per-category writer pattern**
locked at gate-review L8: each observation kind has its own typed
`Observation` dataclass + per-category Postgres adapter living
alongside the owning aggregate, with a category-local `TraversalStore`
Protocol (NOT a shared cross-BC `ObservationStore` port). Future kinds
follow the same shape (`<owning_bc>/aggregates/<agg>/observations.py`).

## Why this lives here, not in `cora.infrastructure.postgres`

The dataclass + Protocol describe Trust BC's domain shape — actor /
command / decision / reason are domain vocabulary, not infrastructure
primitives. The Postgres adapter that knows the SQL also lives here
because the SQL knows the column shape; splitting them across infra
and domain modules would require either a generic SQL builder or
duplicate column lists. Same trade-off the existing `events.py` per-
aggregate modules made (each owns its `to_payload` / `from_stored`).

## Why writes batch from day one

`append_traversals(rows: list[ConduitTraversal])` always takes a
list, even for the realistic "one decision at a time" case (single-
element list). When higher-cardinality observation categories ship
(FrameTrigger, MotorPosition), the shape is unchanged. Locked at
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

TraversalDecision = Literal["Allow", "Deny"]


@dataclass(frozen=True)
class ConduitTraversal:
    """One row in the per-Conduit authz traversal audit log.

    `event_id` is the producer-assigned UUIDv7 identity (matches the
    existing event-sourcing convention). Used as the dedup key under
    at-least-once delivery; UNIQUE constraint enforced at the table
    level. `correlation_id` and `causation_id` thread through from
    the originating command's envelope for full audit traceability
    (gate-review G7 lock).
    """

    event_id: UUID
    conduit_id: UUID
    channel_id: UUID
    actor_id: UUID
    command_name: str
    decision: TraversalDecision
    reason: str | None
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime


class TraversalStore(Protocol):
    """Per-category port for ConduitTraversal observation writes.

    Every Authorize port adapter that wants to emit traversal
    observations (TrustAuthorize today; future authz adapters
    similarly) takes a `TraversalStore` and calls
    `append_traversals(...)` per decision.

    Two implementations: `PostgresTraversalStore` (production) and
    `InMemoryTraversalStore` (tests / `app_env=test`). Both honor
    the same at-least-once contract: callers may retry the same
    `event_id`, the store dedups via the table's PK constraint
    (Postgres) or the in-memory dict (InMemory).
    """

    async def append_traversals(self, rows: list[ConduitTraversal]) -> None: ...


_APPEND_SQL = """
INSERT INTO observations_conduit_traversals (
    event_id, conduit_id, channel_id, actor_id, command_name,
    decision, reason, correlation_id, causation_id, occurred_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresTraversalStore:
    """asyncpg-backed `TraversalStore` implementation.

    Uses `ON CONFLICT (event_id) DO NOTHING` for idempotent retries:
    a producer that re-issues the same `event_id` (after a transient
    network failure on the previous attempt) is a no-op rather than
    a constraint violation. This matches the existing event-store
    UNIQUE-on-event_id pattern.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append_traversals(self, rows: list[ConduitTraversal]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        row.event_id,
                        row.conduit_id,
                        row.channel_id,
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


class InMemoryTraversalStore:
    """Test / `app_env=test` adapter for `TraversalStore`.

    Dict keyed by `event_id` for trivial dedup. Exposes
    `all_traversals()` so contract / unit tests can assert what
    was emitted without going through Postgres.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, ConduitTraversal] = {}

    async def append_traversals(self, rows: list[ConduitTraversal]) -> None:
        for row in rows:
            # ON CONFLICT DO NOTHING semantics: existing wins (matches
            # the Postgres adapter's behavior under retry).
            self._rows.setdefault(row.event_id, row)

    def all_traversals(self) -> list[ConduitTraversal]:
        return list(self._rows.values())


__all__ = [
    "ConduitTraversal",
    "InMemoryTraversalStore",
    "PostgresTraversalStore",
    "TraversalDecision",
    "TraversalStore",
]
