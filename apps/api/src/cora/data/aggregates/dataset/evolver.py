"""Evolver: replay events to reconstruct Dataset state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `DatasetEvent` without a matching match arm here.

Status mapping per event type:
  - `DatasetRegistered` -> REGISTERED  (genesis)
  - `DatasetDiscarded`  -> DISCARDED   (terminal)

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as the rest of the codebase.

**Critical invariant**: every transition arm MUST carry every
Dataset field through from prior state. Constructing
`Dataset(id=..., name=..., uri=..., checksum=..., byte_size=...,
encoding=..., status=...)` without explicitly passing the optional
cross-aggregate refs (`producing_run_id`, `subject_id`,
`derived_from`) would silently WIPE them to defaults (None / empty
frozenset). Aligned to explicit construction post-domain-audit to
match the documented pattern in
Asset/Plan/Method/Practice/Capability/Subject evolvers.

Defensive guard: `DatasetDiscarded` arm raises on `state is None`
(the parent Dataset must exist before the discard event). If a
stream contains DatasetDiscarded without a prior DatasetRegistered,
the stream is corrupted and the evolver fails loud. The
`_require_state` helper keeps per-arm bodies short.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.data.aggregates.dataset.events import (
    DatasetDiscarded,
    DatasetEvent,
    DatasetRegistered,
)
from cora.data.aggregates.dataset.state import (
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetStatus,
    DatasetUri,
)


def _require_state(state: Dataset | None, event_type: str) -> Dataset:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


def evolve(state: Dataset | None, event: DatasetEvent) -> Dataset:
    """Apply one event to the current state."""
    match event:
        case DatasetRegistered(
            dataset_id=dataset_id,
            name=name,
            uri=uri,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            producing_run_id=producing_run_id,
            subject_id=subject_id,
            derived_from=derived_from,
        ):
            _ = state  # DatasetRegistered is the genesis event; prior state ignored.
            return Dataset(
                id=dataset_id,
                name=DatasetName(name),
                uri=DatasetUri(uri),
                checksum=DatasetChecksum(
                    algorithm=checksum_algorithm,
                    value=checksum_value,
                ),
                byte_size=byte_size,
                encoding=DatasetEncoding(
                    media_type=media_type,
                    conforms_to=conforms_to,
                ),
                producing_run_id=producing_run_id,
                subject_id=subject_id,
                derived_from=derived_from,
                status=DatasetStatus.REGISTERED,
            )
        case DatasetDiscarded():
            prior = _require_state(state, "DatasetDiscarded")
            return Dataset(
                id=prior.id,
                name=prior.name,
                uri=prior.uri,
                checksum=prior.checksum,
                byte_size=prior.byte_size,
                encoding=prior.encoding,
                producing_run_id=prior.producing_run_id,
                subject_id=prior.subject_id,
                derived_from=prior.derived_from,
                status=DatasetStatus.DISCARDED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[DatasetEvent]) -> Dataset | None:
    """Replay a stream of events from the empty initial state."""
    state: Dataset | None = None
    for event in events:
        state = evolve(state, event)
    return state
