"""Evolver: replay events to reconstruct Decision state.

8a shipped the genesis arm only. The Decision aggregate is
atomic-immutable for its core (corrections land as new Decisions
with parent_id chains), so the genesis arm is the only state-
producing arm for the choice/reasoning fields.

8c-a adds two logbook lifecycle arms over the
`logbooks: dict[str, UUID]` state shape (mirrors Conduit BC's
6f-5a precedent):

  - `DecisionLogbookOpened` adds `(kind, logbook_id)` to
    `logbooks`, enforcing at-most-one-open-per-kind. Opening a
    second logbook of an existing kind raises
    `DecisionLogbookAlreadyOpenError` carrying the existing id
    so callers can resolve via close-then-reopen if intentional.
  - `DecisionLogbookClosed` finds the kind owning the closed
    `logbook_id` and removes that entry; raises
    `DecisionLogbookNotOpenError` if no kind owns the id.

**Critical invariant**: every transition arm MUST carry every
core Decision field through from prior state, and either preserve
or rewrite `logbooks` deliberately. Constructing `Decision(id=...,
actor_id=..., context=..., choice=...)` without explicitly
passing the additive fields would silently WIPE them to defaults
(None / empty tuple / empty dict). Aligned to explicit construction
post-domain-audit to match the documented pattern in
Asset/Plan/Method/Practice/Family/Subject evolvers.

Defensive guards: both logbook arms raise on `state is None`
(the parent Decision must exist before any logbook can attach
to it). The evolver returns a fresh `Decision` with a new
`logbooks` dict on every logbook-open / logbook-close — the
dict is never mutated in place. Frozen dataclass blocks field
reassignment but not dict mutation; the codebase relies on the
same evolver-purity discipline used by every other aggregate.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.decision.aggregates.decision.events import (
    DecisionEvent,
    DecisionLogbookClosed,
    DecisionLogbookOpened,
    DecisionRated,
    DecisionRegistered,
)
from cora.decision.aggregates.decision.state import (
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionLogbookAlreadyOpenError,
    DecisionLogbookNotOpenError,
    DecisionRatingRecord,
    DecisionRule,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Decision | None, event: DecisionEvent) -> Decision:
    """Apply one event to the current state."""
    match event:
        case DecisionRegistered(
            decision_id=decision_id,
            actor_id=actor_id,
            context=context,
            choice=choice,
            parent_id=parent_id,
            override_kind=override_kind,
            decision_rule=decision_rule,
            reasoning=reasoning,
            confidence=confidence,
            confidence_source=confidence_source,
            alternatives=alternatives,
            decision_inputs=decision_inputs,
            reasoning_signature=reasoning_signature,
        ):
            _ = state  # DecisionRegistered is the genesis event; prior state ignored.
            return Decision(
                id=decision_id,
                actor_id=actor_id,
                context=DecisionContext(context),
                choice=DecisionChoice(choice),
                parent_id=parent_id,
                override_kind=override_kind,
                decision_rule=DecisionRule(decision_rule) if decision_rule is not None else None,
                reasoning=reasoning,
                confidence=confidence,
                confidence_source=confidence_source,
                alternatives=alternatives,
                decision_inputs=decision_inputs,
                reasoning_signature=reasoning_signature,
            )
        case DecisionLogbookOpened(logbook_id=logbook_id, kind=kind):
            prior = require_state(state, "DecisionLogbookOpened")
            existing = prior.logbooks.get(kind)
            if existing is not None:
                raise DecisionLogbookAlreadyOpenError(prior.id, kind, existing)
            return Decision(
                id=prior.id,
                actor_id=prior.actor_id,
                context=prior.context,
                choice=prior.choice,
                parent_id=prior.parent_id,
                override_kind=prior.override_kind,
                decision_rule=prior.decision_rule,
                reasoning=prior.reasoning,
                confidence=prior.confidence,
                confidence_source=prior.confidence_source,
                alternatives=prior.alternatives,
                decision_inputs=prior.decision_inputs,
                reasoning_signature=prior.reasoning_signature,
                logbooks={**prior.logbooks, kind: logbook_id},
                ratings=prior.ratings,
            )
        case DecisionLogbookClosed(logbook_id=logbook_id):
            prior = require_state(state, "DecisionLogbookClosed")
            matching_kind = next(
                (k for k, v in prior.logbooks.items() if v == logbook_id),
                None,
            )
            if matching_kind is None:
                raise DecisionLogbookNotOpenError(prior.id, logbook_id)
            return Decision(
                id=prior.id,
                actor_id=prior.actor_id,
                context=prior.context,
                choice=prior.choice,
                parent_id=prior.parent_id,
                override_kind=prior.override_kind,
                decision_rule=prior.decision_rule,
                reasoning=prior.reasoning,
                confidence=prior.confidence,
                confidence_source=prior.confidence_source,
                alternatives=prior.alternatives,
                decision_inputs=prior.decision_inputs,
                reasoning_signature=prior.reasoning_signature,
                logbooks={k: v for k, v in prior.logbooks.items() if k != matching_kind},
                ratings=prior.ratings,
            )
        case DecisionRated(
            rating=rating,
            comment=comment,
            rated_by_actor_id=rated_by_actor_id,
            rated_at=rated_at,
        ):
            prior = require_state(state, "DecisionRated")
            # Latest-per-actor wins: if a prior rating exists for the
            # same actor, the new one overwrites IFF rated_at is later
            # (defensive: out-of-order replay must not regress state).
            existing = prior.ratings.get(rated_by_actor_id)
            if existing is not None and existing.rated_at >= rated_at:
                # Replay observed an older event after a newer one (rare
                # but possible during projection rebuild). Keep newer.
                return prior
            new_record = DecisionRatingRecord(rating=rating, comment=comment, rated_at=rated_at)
            return Decision(
                id=prior.id,
                actor_id=prior.actor_id,
                context=prior.context,
                choice=prior.choice,
                parent_id=prior.parent_id,
                override_kind=prior.override_kind,
                decision_rule=prior.decision_rule,
                reasoning=prior.reasoning,
                confidence=prior.confidence,
                confidence_source=prior.confidence_source,
                alternatives=prior.alternatives,
                decision_inputs=prior.decision_inputs,
                reasoning_signature=prior.reasoning_signature,
                logbooks=prior.logbooks,
                ratings={**prior.ratings, rated_by_actor_id: new_record},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[DecisionEvent]) -> Decision | None:
    """Replay a stream of events from the empty initial state."""
    state: Decision | None = None
    for event in events:
        state = evolve(state, event)
    return state
