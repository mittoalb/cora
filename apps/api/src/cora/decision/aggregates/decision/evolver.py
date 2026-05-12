"""Evolver: replay events to reconstruct Decision state.

8a shipped the genesis arm only. The Decision aggregate is
atomic-immutable for its core (corrections land as new Decisions
with parent_id chains), so the genesis arm is the only state-
producing arm.

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

Defensive guards: both logbook arms raise on `state is None`
(the parent Decision must exist before any logbook can attach
to it). The evolver returns a fresh `Decision` with a new
`logbooks` dict on every logbook-open / logbook-close — the
dict is never mutated in place. Frozen dataclass blocks field
reassignment but not dict mutation; the codebase relies on the
same evolver-purity discipline used by every other aggregate.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.decision.aggregates.decision.events import (
    DecisionEvent,
    DecisionLogbookClosed,
    DecisionLogbookOpened,
    DecisionRegistered,
)
from cora.decision.aggregates.decision.state import (
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionLogbookAlreadyOpenError,
    DecisionLogbookNotOpenError,
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
        case DecisionLogbookOpened(logbook_id=logbook_id, kind=kind):
            if state is None:
                msg = "DecisionLogbookOpened before DecisionRegistered: stream is corrupted"
                raise ValueError(msg)
            existing = state.logbooks.get(kind)
            if existing is not None:
                raise DecisionLogbookAlreadyOpenError(state.id, kind, existing)
            return replace(state, logbooks={**state.logbooks, kind: logbook_id})
        case DecisionLogbookClosed(logbook_id=logbook_id):
            if state is None:
                msg = "DecisionLogbookClosed before DecisionRegistered: stream is corrupted"
                raise ValueError(msg)
            matching_kind = next(
                (k for k, v in state.logbooks.items() if v == logbook_id),
                None,
            )
            if matching_kind is None:
                raise DecisionLogbookNotOpenError(state.id, logbook_id)
            return replace(
                state,
                logbooks={k: v for k, v in state.logbooks.items() if k != matching_kind},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[DecisionEvent]) -> Decision | None:
    """Replay a stream of events from the empty initial state."""
    state: Decision | None = None
    for event in events:
        state = evolve(state, event)
    return state
