"""RunReading entry: per-Run sensor / motor reading row.

Third concrete entry kind in CORA after `Verdict` (6f-5a)
and `Inference` (8c-b). Mirrors the same per-category writer
pattern: a typed dataclass + per-category Postgres adapter alongside
the owning aggregate, with a category-local `ReadingStore` Protocol
(NOT a shared cross-BC port).

## Polymorphic-with-discriminator

Unlike Verdict (typed `decision: Allow|Deny + reason`) and
Inference (typed 27+ OTel columns), RunReading is
**polymorphic across kinds** via the `sampling_procedure` field. All
RunReading rows share the SAME `(channel_name, value, units?,
sampled_at, ...)` shape regardless of whether they are baseline
snapshots, monitor time-series, or future kinds. This applies the
OGC O&M criterion (typed when value-shape diverges, polymorphic when
uniform) — see [[project_logbook_entry_storage]] for the cross-BC
formulation. The `sampling_procedure` discriminator is W3C SOSA
2023's `sosa:samplingProcedure` slot; values are Bluesky-aligned
operator vocabulary (`baseline`, `monitor`, future-additive
`primary` / `triggered`).

## Three timestamps

  - `sampled_at`: SOSA `phenomenonTime` — when the sensor captured
    the value. For human-entered values, defaults to `occurred_at`
    at the API layer; always populated in storage.
  - `occurred_at`: when the handler appended the entry (CORA Clock
    port; same convention as the events table and other entries).
  - `recorded_at`: when Postgres wrote the row (`DEFAULT now()`;
    same convention as the events table and other entries).

Sensor-derived entries use all three; the dual-time pattern is
documented at [[project_logbook_entry_storage]] §three-timestamp.

## Why writes batch from day one

`append(rows: list[RunReading])` always takes a list, even for the
realistic "one reading at a time" case (single-element list).
Anticipates future DAQ-adapter integration (10a-d) which will batch
naturally. Empty lists are a no-op. Same posture as the prior two
stores.

## Why no read shape today

The `range` query for retrieval lands when a real consumer asks for
it. Today the table is write-only from the application's perspective;
ad-hoc SQL covers any operator queries. Same posture as the prior
two entry kinds.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter class. The dataclass + Protocol stay strictly typed for
# every caller above the boundary.

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class RunReading:
    """One row in the per-Run reading logbook.

    Polymorphic by `sampling_procedure` (SOSA discriminator); all
    kinds (baseline, monitor, ...) share this row shape. `event_id`
    is the producer-assigned UUIDv7 identity (matches the existing
    event-sourcing convention). Used as the dedup key under at-least-
    once delivery; PRIMARY KEY at the table level handles the
    Postgres-side dedup. `correlation_id` and `causation_id` thread
    through from the originating command's envelope for full audit
    traceability.
    """

    event_id: UUID
    run_id: UUID
    logbook_id: UUID
    actor_id: UUID
    command_name: str
    channel_name: str
    value: float
    units: str | None
    sampling_procedure: str
    sampled_at: datetime
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None


class ReadingStore(Protocol):
    """Per-category port for RunReading entry writes.

    The `append_run_readings` handler (and any future Run-side reading
    writer, for example a future DAQ adapter) takes a
    `ReadingStore` and calls `append(...)` per batch.

    Two implementations: `PostgresReadingStore` (production) and
    `InMemoryReadingStore` (tests / `app_env=test`). Both honor the
    same at-least-once contract: callers may retry the same
    `event_id`, the store dedups via the table's PK constraint
    (Postgres) or the in-memory dict (InMemory).
    """

    async def append(self, rows: list[RunReading]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_run_readings (
    event_id, run_id, logbook_id, actor_id, command_name,
    channel_name, value, units, sampling_procedure,
    sampled_at, occurred_at, correlation_id, causation_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresReadingStore:
    """asyncpg-backed `ReadingStore` implementation.

    Uses `ON CONFLICT (event_id) DO NOTHING` for idempotent retries:
    a producer that re-issues the same `event_id` (after a transient
    network failure on the previous attempt) is a no-op rather than
    a constraint violation. Matches the precedent set by
    `PostgresVerdictStore` and `PostgresInferenceStore`.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[RunReading]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        row.event_id,
                        row.run_id,
                        row.logbook_id,
                        row.actor_id,
                        row.command_name,
                        row.channel_name,
                        row.value,
                        row.units,
                        row.sampling_procedure,
                        row.sampled_at,
                        row.occurred_at,
                        row.correlation_id,
                        row.causation_id,
                    )
                    for row in rows
                ],
            )


class InMemoryReadingStore:
    """Test / `app_env=test` adapter for `ReadingStore`.

    Dict keyed by `event_id` for trivial dedup. Exposes `all()` so
    contract / unit tests can assert what was emitted without going
    through Postgres.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, RunReading] = {}

    async def append(self, rows: list[RunReading]) -> None:
        for row in rows:
            # ON CONFLICT DO NOTHING semantics: existing wins (matches
            # the Postgres adapter's behavior under retry).
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[RunReading]:
        return list(self._rows.values())


__all__ = [
    "InMemoryReadingStore",
    "PostgresReadingStore",
    "ReadingStore",
    "RunReading",
]
