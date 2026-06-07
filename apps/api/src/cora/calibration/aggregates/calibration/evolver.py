"""Evolver: replay events to reconstruct Calibration state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CalibrationEvent` without a matching match arm here.

Two events fold:

  - `CalibrationDefined`           -> genesis (revisions empty)
  - `CalibrationRevisionAppended`  -> append revision

Per [[project_fold_symmetry_design]], `defined_at` is folded onto
`Calibration` from `CalibrationDefined.occurred_at` to pair with the
folded `defined_by` attribution. `last_revised_at` continues to live
only on the projection (Path C) because the per-revision attribution
sits on `CalibrationRevision.established_by` rather than on the
parent aggregate. Per-revision `established_at` STAYS on
`CalibrationRevision` — it is a domain-meaningful timestamp (when
the revision was decided, may differ from when the event was
recorded) and pairs with `established_by`.

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.calibration.aggregates.calibration.events import (
    CalibrationDefined,
    CalibrationEvent,
    CalibrationRevisionAppended,
    CalibrationRevisionPublished,
    deserialize_source,
)
from cora.calibration.aggregates.calibration.state import (
    Calibration,
    CalibrationRevision,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Calibration | None, event: CalibrationEvent) -> Calibration:
    """Apply one event to the current state."""
    match event:
        case CalibrationDefined(
            calibration_id=calibration_id,
            target_id=target_id,
            quantity=quantity,
            operating_point=operating_point,
            description=description,
            defined_by=defined_by,
            occurred_at=occurred_at,
        ):
            _ = state  # CalibrationDefined is the genesis event; prior state ignored
            # Shallow-copy operating_point so payload mutation can't alias state (B1).
            # Fold-symmetry pair: defined_at <- occurred_at, defined_by <- defined_by.
            return Calibration(
                id=calibration_id,
                target_id=target_id,
                quantity=quantity,
                operating_point=dict(operating_point),
                description=description,
                revisions=(),
                defined_at=occurred_at,
                defined_by=defined_by,
            )
        case CalibrationRevisionAppended(
            revision_id=revision_id,
            calibration_id=_calibration_id,
            value=value,
            status=status,
            source_procedure_id=source_procedure_id,
            source_dataset_id=source_dataset_id,
            asserted_by=asserted_by,
            established_at=established_at,
            established_by=established_by,
            decided_by_decision_id=decided_by_decision_id,
            supersedes_revision_id=supersedes_revision_id,
            content_hash=content_hash,
        ):
            prior = require_state(state, "CalibrationRevisionAppended")
            # Reconstruct typed CalibrationSource via the public
            # deserialize helper (exclusive-arc check enforced).
            source = deserialize_source(
                {
                    "source_procedure_id": (
                        str(source_procedure_id) if source_procedure_id is not None else None
                    ),
                    "source_dataset_id": (
                        str(source_dataset_id) if source_dataset_id is not None else None
                    ),
                    "asserted_by": (str(asserted_by) if asserted_by is not None else None),
                }
            )
            revision = CalibrationRevision(
                revision_id=revision_id,
                # Shallow-copy value so payload mutation can't alias revision (B1).
                value=dict(value),
                status=status,  # already a CalibrationStatus enum from event class
                source=source,
                established_at=established_at,
                established_by=established_by,
                decided_by_decision_id=decided_by_decision_id,
                supersedes_revision_id=supersedes_revision_id,
                content_hash=content_hash,
            )
            return Calibration(
                id=prior.id,
                target_id=prior.target_id,
                quantity=prior.quantity,
                operating_point=prior.operating_point,
                description=prior.description,
                revisions=(*prior.revisions, revision),
                defined_at=prior.defined_at,
                defined_by=prior.defined_by,
            )
        case CalibrationRevisionPublished():
            prior = require_state(state, "CalibrationRevisionPublished")
            return prior
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CalibrationEvent]) -> Calibration | None:
    """Replay a stream of events from the empty initial state."""
    state: Calibration | None = None
    for event in events:
        state = evolve(state, event)
    return state
