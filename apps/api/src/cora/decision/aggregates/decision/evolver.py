"""Evolver: replay events to reconstruct Decision state.

8a ships the genesis arm only. The aggregate is atomic-immutable
(no transitions; corrections land as new Decisions with parent_id
chains), so the evolver remains tiny by design, `assert_never`
catches any future event type added without an arm.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.decision.aggregates.decision.events import (
    DecisionEvent,
    DecisionRegistered,
)
from cora.decision.aggregates.decision.state import (
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionRule,
)


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
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[DecisionEvent]) -> Decision | None:
    """Replay a stream of events from the empty initial state."""
    state: Decision | None = None
    for event in events:
        state = evolve(state, event)
    return state
