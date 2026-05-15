"""Evolver: replay events to reconstruct Clearance state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type is
added to `ClearanceEvent` without a matching match arm here.

Status mapping per event type:
  - `ClearanceRegistered`         -> DEFINED       (genesis)
  - `ClearanceSubmitted`          -> SUBMITTED
  - `ClearanceUnderReview`        -> UNDER_REVIEW
  - `ClearanceReviewStepRecorded` -> (no status change; appends reviewers tuple)
  - `ClearanceApproved`           -> APPROVED (sets valid_from / valid_until /
                                     last_reviewed_by_actor_id)
  - `ClearanceRejected`           -> REJECTED (sets last_reviewed_by_actor_id)
  - `ClearanceActivated`          -> ACTIVE

Phase 11a-c will add:
  - `ClearanceExpired`              -> EXPIRED
  - `ClearanceAmendmentInitiated`   -> (no status change; metadata only)
  - `ClearanceSuperseded`           -> SUPERSEDED

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver` (hoisted
post-7e at the 11th identical-copy site).
"""

from collections.abc import Sequence
from datetime import datetime  # noqa: TC003  (used in inline type hints inside helpers)
from typing import assert_never
from uuid import UUID  # noqa: TC003

from cora.infrastructure.evolver import require_state
from cora.safety.aggregates.clearance.events import (
    ClearanceActivated,
    ClearanceApproved,
    ClearanceEvent,
    ClearanceRegistered,
    ClearanceRejected,
    ClearanceReviewStepRecorded,
    ClearanceSubmitted,
    ClearanceUnderReview,
    deserialize_binding,
    deserialize_declaration,
)
from cora.safety.aggregates.clearance.state import (
    Clearance,
    ClearanceKind,
    ClearanceStatus,
    ClearanceTitle,
    ReviewerStep,
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
        case ClearanceSubmitted():
            prior = require_state(state, "ClearanceSubmitted")
            return _replace_status(prior, ClearanceStatus.SUBMITTED)
        case ClearanceUnderReview():
            prior = require_state(state, "ClearanceUnderReview")
            return _replace_status(prior, ClearanceStatus.UNDER_REVIEW)
        case ClearanceReviewStepRecorded(
            step_index=step_index,
            role=role,
            actor_id=actor_id,
            decision=decision,
            decided_at=decided_at,
            notes=notes,
        ):
            prior = require_state(state, "ClearanceReviewStepRecorded")
            new_step = ReviewerStep(
                step_index=step_index,
                role=role,
                actor_id=actor_id,
                decision=decision,
                decided_at=decided_at,
                notes=notes,
            )
            return _replace_reviewers(prior, (*prior.reviewers, new_step))
        case ClearanceApproved(
            approving_actor_id=actor_id,
            valid_from=valid_from,
            valid_until=valid_until,
        ):
            prior = require_state(state, "ClearanceApproved")
            return _replace_approved(
                prior,
                approving_actor_id=actor_id,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        case ClearanceRejected(rejecting_actor_id=actor_id):
            prior = require_state(state, "ClearanceRejected")
            return _replace_status(
                prior,
                ClearanceStatus.REJECTED,
                last_reviewed_by_actor_id=actor_id,
            )
        case ClearanceActivated():
            prior = require_state(state, "ClearanceActivated")
            return _replace_status(prior, ClearanceStatus.ACTIVE)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _replace_status(
    prior: Clearance,
    new_status: ClearanceStatus,
    *,
    last_reviewed_by_actor_id: "UUID | None" = None,
) -> Clearance:
    """Return a new Clearance with `status` updated; identity + most fields preserved."""
    return Clearance(
        id=prior.id,
        kind=prior.kind,
        facility_asset_id=prior.facility_asset_id,
        title=prior.title,
        bindings=prior.bindings,
        declarations=prior.declarations,
        risk_band=prior.risk_band,
        reviewers=prior.reviewers,
        status=new_status,
        external_id=prior.external_id,
        parent_clearance_id=prior.parent_clearance_id,
        valid_from=prior.valid_from,
        valid_until=prior.valid_until,
        next_review_due_at=prior.next_review_due_at,
        last_reviewed_by_actor_id=(
            last_reviewed_by_actor_id
            if last_reviewed_by_actor_id is not None
            else prior.last_reviewed_by_actor_id
        ),
    )


def _replace_reviewers(prior: Clearance, new_reviewers: tuple[ReviewerStep, ...]) -> Clearance:
    """Return a new Clearance with `reviewers` updated; status preserved."""
    return Clearance(
        id=prior.id,
        kind=prior.kind,
        facility_asset_id=prior.facility_asset_id,
        title=prior.title,
        bindings=prior.bindings,
        declarations=prior.declarations,
        risk_band=prior.risk_band,
        reviewers=new_reviewers,
        status=prior.status,
        external_id=prior.external_id,
        parent_clearance_id=prior.parent_clearance_id,
        valid_from=prior.valid_from,
        valid_until=prior.valid_until,
        next_review_due_at=prior.next_review_due_at,
        last_reviewed_by_actor_id=prior.last_reviewed_by_actor_id,
    )


def _replace_approved(
    prior: Clearance,
    *,
    approving_actor_id: "UUID",
    valid_from: "datetime | None",
    valid_until: "datetime | None",
) -> Clearance:
    """Return a new Clearance after Approved transition: status APPROVED,
    valid_from / valid_until overwritten if explicit values provided,
    last_reviewed_by_actor_id set to the approving actor."""
    return Clearance(
        id=prior.id,
        kind=prior.kind,
        facility_asset_id=prior.facility_asset_id,
        title=prior.title,
        bindings=prior.bindings,
        declarations=prior.declarations,
        risk_band=prior.risk_band,
        reviewers=prior.reviewers,
        status=ClearanceStatus.APPROVED,
        external_id=prior.external_id,
        parent_clearance_id=prior.parent_clearance_id,
        valid_from=valid_from if valid_from is not None else prior.valid_from,
        valid_until=valid_until if valid_until is not None else prior.valid_until,
        next_review_due_at=prior.next_review_due_at,
        last_reviewed_by_actor_id=approving_actor_id,
    )


def fold(events: Sequence[ClearanceEvent]) -> Clearance | None:
    """Replay a stream of events from the empty initial state."""
    state: Clearance | None = None
    for event in events:
        state = evolve(state, event)
    return state
