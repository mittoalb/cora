"""The `AppendRunReadings` command, intent dataclass for this slice.

Batch shape from day one (matches `append_reasoning_entries`
precedent from Decision BC). Length-1 batches are the degenerate
case; same code path either way. Anticipates DAQ-adapter
integration which will batch naturally.

Producer-supplied `event_id` (UUIDv7) per entry; store dedups via
Postgres PK (`ON CONFLICT (event_id) DO NOTHING`). At-least-once
semantics for free.

## Lazy open-on-first-write

The handler loads the parent Run, checks whether
`run.reading_logbook_id` is set, and emits a
`RunReadingLogbookOpened` event lazily on first write. `start_run`
stays unchanged; the logbook attaches when the first
reading arrives. Per [[project_run_reading_design]] §Decision and
[[project_logbook_entry_storage]].

## Polymorphic by sampling_procedure

All entries share the same row shape `(channel_name, value, units?,
sampled_at, sampling_procedure)`. The `sampling_procedure` field
discriminates baseline vs monitor vs future-additive kinds. SOSA-
aligned (W3C SOSA 2023 `sosa:samplingProcedure`).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RunReadingInput:
    """One reading entry's input payload from the producer.

    Mirrors `RunReading` but omits the CORA-infra fields (run_id /
    logbook_id / actor_id / command_name / correlation_id /
    causation_id) which are populated by the handler from the URL
    path + envelope.
    """

    event_id: UUID
    channel_name: str
    value: float
    sampled_at: datetime
    sampling_procedure: str
    units: str | None = None
    occurred_at: datetime | None = None
    """When the handler appended the entry. Optional from the producer
    — when omitted, the handler defaults to `clock.now()`. Producers
    that have a separate ingest-time clock (DAQ adapters with their
    own buffering) can populate this explicitly."""


@dataclass(frozen=True)
class AppendRunReadings:
    """Append a batch of readings to a Run's reading logbook."""

    run_id: UUID
    entries: tuple[RunReadingInput, ...]
