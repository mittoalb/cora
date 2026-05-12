"""Evolver: replay events to reconstruct Dataset state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `DatasetEvent` without a matching match arm here.

Status mapping per event type:
  - `DatasetRegistered` -> REGISTERED  (genesis)

7b extends with:
  - `DatasetDiscarded`  -> DISCARDED   (terminal)

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as the rest of the codebase.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.data.aggregates.dataset.events import (
    DatasetEvent,
    DatasetRegistered,
)
from cora.data.aggregates.dataset.state import (
    Dataset,
    DatasetName,
    DatasetStatus,
    DatasetUri,
)


def evolve(state: Dataset | None, event: DatasetEvent) -> Dataset:
    """Apply one event to the current state."""
    match event:
        case DatasetRegistered(
            dataset_id=dataset_id,
            name=name,
            uri=uri,
            checksum=checksum,
            byte_size=byte_size,
            format=format_,
            producing_run_id=producing_run_id,
            subject_id=subject_id,
            derived_from=derived_from,
        ):
            _ = state  # DatasetRegistered is the genesis event; prior state ignored.
            return Dataset(
                id=dataset_id,
                name=DatasetName(name),
                uri=DatasetUri(uri),
                checksum=checksum,
                byte_size=byte_size,
                format=format_,
                producing_run_id=producing_run_id,
                subject_id=subject_id,
                derived_from=derived_from,
                status=DatasetStatus.REGISTERED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[DatasetEvent]) -> Dataset | None:
    """Replay a stream of events from the empty initial state."""
    state: Dataset | None = None
    for event in events:
        state = evolve(state, event)
    return state
