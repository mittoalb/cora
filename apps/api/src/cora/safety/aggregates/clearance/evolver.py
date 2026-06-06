"""Evolver: replay events to reconstruct Clearance state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type is
added to `ClearanceEvent` without a matching match arm here.

Status mapping per event type:
  - `ClearanceRegistered`         -> DEFINED       (genesis)
  - `ClearanceSubmitted`          -> SUBMITTED
  - `ClearanceReviewStarted`      -> UNDER_REVIEW
  - `ClearanceReviewStepAppended` -> (no status change; appends review_steps tuple)
  - `ClearanceApproved`           -> APPROVED (sets valid_from / valid_until
                                     overrides if explicit values provided)
  - `ClearanceRejected`           -> REJECTED
  - `ClearanceActivated`          -> ACTIVE
  - `ClearanceExpired`            -> EXPIRED
  - `ClearanceSuperseded`         -> SUPERSEDED (written to PARENT stream
                                     when `amend_clearance` creates a
                                     successor child)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver` (hoisted
at the rule-of-three trigger at the 11th identical-copy site).
"""

from collections.abc import Sequence
from datetime import datetime  # noqa: TC003  (used in inline type hints inside helpers)
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.safety.aggregates.clearance.events import (
    ClearanceActivated,
    ClearanceApproved,
    ClearanceEvent,
    ClearanceExpired,
    ClearanceRegistered,
    ClearanceRejected,
    ClearanceReviewStarted,
    ClearanceReviewStepAppended,
    ClearanceSubmitted,
    ClearanceSuperseded,
    deserialize_binding,
    deserialize_declaration,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.aggregates.clearance.state import (
    Clearance,
    ClearanceKind,
    ClearanceStatus,
    ClearanceTitle,
    ReviewStep,
)


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
            parent_id=parent_id,
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
                review_steps=(),
                status=ClearanceStatus.DEFINED,
                external_id=external_id,
                parent_id=parent_id,
                valid_from=valid_from,
                valid_until=valid_until,
                next_review_due_at=None,
            )
        case ClearanceSubmitted():
            prior = require_state(state, "ClearanceSubmitted")
            return _replace_status(prior, ClearanceStatus.SUBMITTED)
        case ClearanceReviewStarted():
            prior = require_state(state, "ClearanceReviewStarted")
            return _replace_status(prior, ClearanceStatus.UNDER_REVIEW)
        case ClearanceReviewStepAppended(
            step_index=step_index,
            role=role,
            actor_id=actor_id,
            decision=decision,
            decided_at=decided_at,
            notes=notes,
        ):
            prior = require_state(state, "ClearanceReviewStepAppended")
            new_step = ReviewStep(
                step_index=step_index,
                role=role,
                actor_id=actor_id,
                decision=decision,
                decided_at=decided_at,
                notes=notes,
            )
            return _replace_review_steps(prior, (*prior.review_steps, new_step))
        case ClearanceApproved(
            valid_from=valid_from,
            valid_until=valid_until,
        ):
            prior = require_state(state, "ClearanceApproved")
            return _replace_approved(
                prior,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        case ClearanceRejected():
            prior = require_state(state, "ClearanceRejected")
            return _replace_status(prior, ClearanceStatus.REJECTED)
        case ClearanceActivated():
            prior = require_state(state, "ClearanceActivated")
            return _replace_status(prior, ClearanceStatus.ACTIVE)
        case ClearanceExpired():
            prior = require_state(state, "ClearanceExpired")
            return _replace_status(prior, ClearanceStatus.EXPIRED)
        case ClearanceSuperseded():
            prior = require_state(state, "ClearanceSuperseded")
            return _replace_status(prior, ClearanceStatus.SUPERSEDED)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _replace_status(prior: Clearance, new_status: ClearanceStatus) -> Clearance:
    """Return a new Clearance with `status` updated; identity + most fields preserved."""
    return Clearance(
        id=prior.id,
        kind=prior.kind,
        facility_asset_id=prior.facility_asset_id,
        title=prior.title,
        bindings=prior.bindings,
        declarations=prior.declarations,
        risk_band=prior.risk_band,
        review_steps=prior.review_steps,
        status=new_status,
        external_id=prior.external_id,
        parent_id=prior.parent_id,
        valid_from=prior.valid_from,
        valid_until=prior.valid_until,
        next_review_due_at=prior.next_review_due_at,
    )


def _replace_review_steps(prior: Clearance, new_review_steps: tuple[ReviewStep, ...]) -> Clearance:
    """Return a new Clearance with `review_steps` updated; status preserved."""
    return Clearance(
        id=prior.id,
        kind=prior.kind,
        facility_asset_id=prior.facility_asset_id,
        title=prior.title,
        bindings=prior.bindings,
        declarations=prior.declarations,
        risk_band=prior.risk_band,
        review_steps=new_review_steps,
        status=prior.status,
        external_id=prior.external_id,
        parent_id=prior.parent_id,
        valid_from=prior.valid_from,
        valid_until=prior.valid_until,
        next_review_due_at=prior.next_review_due_at,
    )


def _replace_approved(
    prior: Clearance,
    *,
    valid_from: "datetime | None",
    valid_until: "datetime | None",
) -> Clearance:
    """Return a new Clearance after Approved transition: status APPROVED,
    valid_from / valid_until overwritten if explicit values provided."""
    return Clearance(
        id=prior.id,
        kind=prior.kind,
        facility_asset_id=prior.facility_asset_id,
        title=prior.title,
        bindings=prior.bindings,
        declarations=prior.declarations,
        risk_band=prior.risk_band,
        review_steps=prior.review_steps,
        status=ClearanceStatus.APPROVED,
        external_id=prior.external_id,
        parent_id=prior.parent_id,
        valid_from=valid_from if valid_from is not None else prior.valid_from,
        valid_until=valid_until if valid_until is not None else prior.valid_until,
        next_review_due_at=prior.next_review_due_at,
    )


def fold(events: Sequence[ClearanceEvent]) -> Clearance | None:
    """Replay a stream of events from the empty initial state."""
    state: Clearance | None = None
    for event in events:
        state = evolve(state, event)
    return state
