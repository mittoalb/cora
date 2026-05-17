"""Pure decider for the `re_debrief_run` slice (Phase 8f-c iter 1).

Composes the `DecisionRegistered` event for an on-demand RunDebrief
invocation. Pure function: given the operator inputs + LLM response
+ pre-loaded Actor + chosen `decision_id`, returns the event to
append. No I/O, no awaits, no clock / id-generator calls.

## Why a separate decider

The cross-BC slice-contract test
(`tests/architecture/test_slice_contract.py`) requires `decider.py`
for every command slice. The cross-BC gate-review P1 (8f-c iter 1)
additionally noted that the LLM-response-to-`DecisionRegistered`
mapping is genuinely pure and benefits from extraction: a future
on-demand agent slice (8f-c iter 2 / 8f-c+) and a Pattern B
subscriber would both consume the same shape.

The 8f-b iter 2b subscriber (`cora.agent.subscribers.run_debrief`)
currently inlines an equivalent composition. Rule-of-three trigger
to hoist this decider out of the slice and into a shared module
(eg. `cora.agent.deciders.run_debrief`) fires when EITHER a second
on-demand agent slice ships OR the subscriber's composition is
refactored to call through this decider.

## Cross-aggregate validation

The decider does NOT load aggregates -- the handler pre-loads
Run + Agent's Actor + parent Decision. The decider trusts the
handler:

  - `actor` is non-None (handler raised AgentNotSeededError otherwise).
  - `actor.is_active` is True (handler raised AgentDeactivatedError
    otherwise).
  - `parent_decision_id` (when set) points at a real Decision in
    the same Run AND with `context = "RunDebrief"` (handler raised
    ParentDecisionMissingError / ParentDecisionRunMismatchError /
    ParentDecisionAgentMismatchError otherwise).

## Field validation

Decision BC's public VOs + helpers do the per-field check:
`DecisionChoice` / `DecisionContext` / `DecisionRule` raise their
own `Invalid<X>Error` on bad input. `validate_reasoning` /
`validate_confidence` / `validate_decision_inputs` likewise.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from cora.access.aggregates.actor import Actor
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    validate_confidence,
    validate_decision_inputs,
    validate_reasoning,
)

_DECISION_RULE = "agent:RunDebrief:v1"


def decide(
    *,
    new_id: UUID,
    actor: Actor,
    run_id: UUID,
    parent_decision_id: UUID | None,
    choice: str,
    confidence: float | None,
    reasoning: str,
    occurred_at: datetime,
    extra_decision_inputs: dict[str, Any] | None = None,
) -> DecisionRegistered:
    """Compose the on-demand RunDebrief `DecisionRegistered` event.

    `choice` is constrained at the projection layer (and by the
    LLM's structured output schema) to the closed 6-value set, but
    the Decision BC's open-string `DecisionChoice` VO is used here
    so the decider stays vocabulary-agnostic.

    `extra_decision_inputs` merges into the base inputs after the
    base keys are set; collisions on `run_id` / `trigger` /
    `prompt_template_id` are silently overwritten by the extra dict
    (intentional: callers supplying these keys override on purpose,
    eg. the DebriefDeferred path's `failure_error_class`).
    """
    decision_choice = DecisionChoice(choice)
    decision_context = DecisionContext(DECISION_CONTEXT_RUN_DEBRIEF)
    decision_rule = DecisionRule(_DECISION_RULE)
    base_inputs: dict[str, Any] = {
        "run_id": str(run_id),
        "trigger": "on-demand",
        "prompt_template_id": str(RUN_DEBRIEF_PROMPT_TEMPLATE_ID),
    }
    if extra_decision_inputs:
        base_inputs.update(extra_decision_inputs)
    decision_inputs = validate_decision_inputs(base_inputs)
    validated_reasoning = validate_reasoning(reasoning)
    validated_confidence = validate_confidence(confidence)

    return DecisionRegistered(
        decision_id=new_id,
        actor_id=actor.id,
        context=decision_context.value,
        choice=decision_choice.value,
        parent_id=parent_decision_id,
        override_kind=None,
        decision_rule=decision_rule.value,
        reasoning=validated_reasoning,
        confidence=validated_confidence,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        decision_inputs=decision_inputs,
        reasoning_signature=None,
        occurred_at=occurred_at,
    )


__all__ = ["decide"]
