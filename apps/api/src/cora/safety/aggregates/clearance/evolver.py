"""Evolver: replay events to reconstruct Clearance state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type is
added to `ClearanceEvent` without a matching match arm here.

Status mapping per event type:
  - `ClearanceRegistered` -> DEFINED  (genesis; FSM Defined-only at 11a-a)

Phase 11a-b will add:
  - `ClearanceSubmitted`            -> SUBMITTED
  - `ClearanceUnderReview`          -> UNDER_REVIEW
  - `ClearanceReviewStepRecorded`   -> (no status change; appends reviewers tuple)
  - `ClearanceApproved`             -> APPROVED
  - `ClearanceRejected`             -> REJECTED
  - `ClearanceActivated`            -> ACTIVE

Phase 11a-c will add:
  - `ClearanceExpired`              -> EXPIRED
  - `ClearanceAmendmentInitiated`   -> (no status change; metadata only)
  - `ClearanceSuperseded`           -> SUPERSEDED

The mapping is hardcoded per match arm; the event type IS the
state-change indicator. Same precedent as `CapabilityDefined ->
DEFINED` / `SubjectMounted -> MOUNTED` / `SupplyRegistered -> UNKNOWN`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.safety.aggregates.clearance.events import (
    ClearanceEvent,
    ClearanceRegistered,
    deserialize_binding,
    deserialize_declaration,
)
from cora.safety.aggregates.clearance.state import (
    Clearance,
    ClearanceKind,
    ClearanceStatus,
    ClearanceTitle,
)
from cora.safety.hazard_classification import RiskBand


def evolve(state: Clearance | None, event: ClearanceEvent) -> Clearance:
    """Apply one event to the current state."""
    match event:
        case ClearanceRegistered(
            clearance_id=clearance_id,
            kind=kind,
            facility_asset_id=facility_asset_id,
            title=title,
            bindings=bindings,
            declarations=declarations,
            risk_band=risk_band,
            external_id=external_id,
            valid_from=valid_from,
            valid_until=valid_until,
            parent_clearance_id=parent_clearance_id,
        ):
            _ = state  # ClearanceRegistered is the genesis event; prior state ignored
            return Clearance(
                id=clearance_id,
                kind=ClearanceKind(kind),
                facility_asset_id=facility_asset_id,
                title=ClearanceTitle(title),
                bindings=frozenset(deserialize_binding(b) for b in bindings),
                declarations=frozenset(deserialize_declaration(d) for d in declarations),
                risk_band=RiskBand(risk_band) if risk_band is not None else None,
                reviewers=(),
                status=ClearanceStatus.DEFINED,
                external_id=external_id,
                parent_clearance_id=parent_clearance_id,
                valid_from=valid_from,
                valid_until=valid_until,
                next_review_due_at=None,
                last_reviewed_by_actor_id=None,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ClearanceEvent]) -> Clearance | None:
    """Replay a stream of events from the empty initial state."""
    state: Clearance | None = None
    for event in events:
        state = evolve(state, event)
    return state
