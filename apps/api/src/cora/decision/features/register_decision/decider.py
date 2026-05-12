"""Pure decider for the `RegisterDecision` command.

Pure function: given the (always None) Decision state, a
`RegisterDecision` command, and a pre-loaded
`DecisionRegistrationContext`, returns the events to append. No
I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Cross-aggregate validation (gate-review Q2 lock B)

Existence-only checks; the decider trusts the handler's loads.
The handler raises `DeciderActorNotFoundError` upstream if the
Actor doesn't exist (and `context.actor: Actor` is non-Optional
to make the contract explicit at the type boundary). The decider
checks only the parent-Decision branch because parent_id is
conditional:

  - If `command.parent_id` is set, `context.parent` must be
    non-None (handler raises `ParentDecisionNotFoundError`
    upstream; this branch is the decider-level statement of the
    contract for the conditional case).

No status checks: a Decision can be made by any Actor including
Deactivated (the historical fact still holds), and any prior
Decision can be the parent in an override chain.

## Override-kind invariant (gate-review L15)

`override_kind` only makes sense with a `parent_id`. The decider
raises `OverrideKindRequiresParentError` if the command has
`override_kind` set but `parent_id` is None.

## VO trim semantics

Field VOs (`DecisionChoice`, `DecisionContext`, `DecisionRule`)
handle their own trimming + validation in `__post_init__`. The
optional fields use top-level `validate_*` helpers because they
have no other invariants beyond shape.
"""

from datetime import datetime
from uuid import UUID

from cora.decision.aggregates.decision import (
    Decision,
    DecisionAlreadyExistsError,
    DecisionChoice,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    OverrideKindRequiresParentError,
    ParentDecisionNotFoundError,
    validate_alternatives,
    validate_confidence,
    validate_decision_inputs,
    validate_reasoning,
    validate_reasoning_signature,
)
from cora.decision.features.register_decision.command import RegisterDecision
from cora.decision.features.register_decision.context import DecisionRegistrationContext


def decide(
    state: Decision | None,
    command: RegisterDecision,
    context: DecisionRegistrationContext,
    *,
    now: datetime,
    new_id: UUID,
) -> list[DecisionRegistered]:
    """Decide the events produced by registering a new Decision."""
    if state is not None:
        raise DecisionAlreadyExistsError(state.id)

    # Cross-agg parent guard (handler raises ParentDecisionNotFoundError
    # upstream; this branch is the decider-level statement of contract
    # for the conditional case).
    if command.parent_id is not None and context.parent is None:
        raise ParentDecisionNotFoundError(command.parent_id)

    # override_kind / parent_id consistency.
    if command.override_kind is not None and command.parent_id is None:
        raise OverrideKindRequiresParentError(command.override_kind)

    # Field-level validation via VOs + helpers.
    choice = DecisionChoice(command.choice)
    decision_context = DecisionContext(command.context)
    decision_rule = (
        DecisionRule(command.decision_rule) if command.decision_rule is not None else None
    )
    reasoning = validate_reasoning(command.reasoning)
    confidence = validate_confidence(command.confidence)
    alternatives = validate_alternatives(command.alternatives)
    decision_inputs = validate_decision_inputs(command.decision_inputs)
    reasoning_signature = validate_reasoning_signature(command.reasoning_signature)

    return [
        DecisionRegistered(
            decision_id=new_id,
            actor_id=command.actor_id,
            context=decision_context.value,
            choice=choice.value,
            parent_id=command.parent_id,
            override_kind=command.override_kind,
            decision_rule=decision_rule.value if decision_rule is not None else None,
            reasoning=reasoning,
            confidence=confidence,
            confidence_source=command.confidence_source,
            alternatives=alternatives,
            decision_inputs=decision_inputs,
            reasoning_signature=reasoning_signature,
            occurred_at=now,
        )
    ]
