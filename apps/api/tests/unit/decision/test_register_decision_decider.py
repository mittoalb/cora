"""Unit tests for the `register_decision` slice's pure decider."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import Actor, ActorName
from cora.decision.aggregates.decision import (
    Decision,
    DecisionAlreadyExistsError,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    InvalidDecisionAlternativesError,
    InvalidDecisionChoiceError,
    InvalidDecisionConfidenceError,
    InvalidDecisionContextError,
    InvalidDecisionInputsError,
    InvalidDecisionReasoningError,
    InvalidDecisionRuleError,
    OverrideKindRequiresParentError,
    ParentDecisionNotFoundError,
)
from cora.decision.features import register_decision
from cora.decision.features.register_decision import (
    DecisionRegistrationContext,
    RegisterDecision,
)

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _actor() -> Actor:
    return Actor(id=uuid4(), name=ActorName("Operator"))


def _good_command(**overrides: Any) -> RegisterDecision:
    base: dict[str, Any] = {
        "actor_id": uuid4(),
        "context": "RecipeApproval",
        "choice": "Approved",
        "parent_id": None,
        "override_kind": None,
        "decision_rule": None,
        "reasoning": None,
        "confidence": None,
        "confidence_source": None,
        "alternatives": (),
        "decision_inputs": None,
        "reasoning_signature": None,
    }
    base.update(overrides)
    return RegisterDecision(**base)


def _existing_decision() -> Decision:
    return Decision(
        id=uuid4(),
        actor_id=uuid4(),
        context=DecisionContext("RecipeApproval"),
        choice=DecisionChoice("Approved"),
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_decision_registered_with_minimum_fields() -> None:
    new_id = uuid4()
    actor_id = uuid4()
    cmd = _good_command(actor_id=actor_id)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.decision_id == new_id
    assert event.actor_id == actor_id
    assert event.context == "RecipeApproval"
    assert event.choice == "Approved"
    assert event.parent_id is None
    assert event.override_kind is None
    assert event.alternatives == ()
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_choice_via_value_object() -> None:
    cmd = _good_command(choice="  trimmed  ")
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].choice == "trimmed"


@pytest.mark.unit
def test_decide_passes_optional_fields_through() -> None:
    parent_id = uuid4()
    cmd = _good_command(
        parent_id=parent_id,
        override_kind="exception",
        decision_rule="iso17025:7.1.3:simple_acceptance",
        reasoning="Operator override after re-check.",
        confidence=0.85,
        confidence_source=DecisionConfidenceSource.HUMAN,
        alternatives=("Approve", "Reject", "Re-measure"),
        decision_inputs={"measured": 1.2, "limit": 1.5},
        reasoning_signature="sha256:abc",
    )
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor(), parent=_existing_decision()),
        now=_NOW,
        new_id=uuid4(),
    )
    e = events[0]
    assert e.parent_id == parent_id
    assert e.override_kind == "exception"
    assert e.decision_rule == "iso17025:7.1.3:simple_acceptance"
    assert e.reasoning == "Operator override after re-check."
    assert e.confidence == 0.85
    assert e.confidence_source is DecisionConfidenceSource.HUMAN
    assert e.alternatives == ("Approve", "Reject", "Re-measure")
    assert e.decision_inputs == {"measured": 1.2, "limit": 1.5}
    assert e.reasoning_signature == "sha256:abc"


# ---------- Field validation ----------


@pytest.mark.unit
def test_decide_raises_invalid_choice_for_blank() -> None:
    cmd = _good_command(choice="   ")
    with pytest.raises(InvalidDecisionChoiceError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_context_for_blank() -> None:
    cmd = _good_command(context="")
    with pytest.raises(InvalidDecisionContextError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_rule_for_blank() -> None:
    cmd = _good_command(decision_rule="   ")
    with pytest.raises(InvalidDecisionRuleError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_reasoning_for_too_long() -> None:
    cmd = _good_command(reasoning="a" * 6000)
    with pytest.raises(InvalidDecisionReasoningError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_confidence_out_of_range() -> None:
    cmd = _good_command(confidence=1.5)
    with pytest.raises(InvalidDecisionConfidenceError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_alternatives_for_blank_entry() -> None:
    cmd = _good_command(alternatives=("Hold", "", "Stop"))
    with pytest.raises(InvalidDecisionAlternativesError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_inputs_for_blank_key() -> None:
    cmd = _good_command(decision_inputs={"": 1})
    with pytest.raises(InvalidDecisionInputsError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- override_kind / parent_id consistency ----------


@pytest.mark.unit
def test_decide_raises_override_kind_requires_parent_when_no_parent() -> None:
    cmd = _good_command(override_kind="correction")
    with pytest.raises(OverrideKindRequiresParentError) as exc_info:
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.override_kind == "correction"


@pytest.mark.unit
def test_decide_accepts_parent_without_override_kind() -> None:
    """Parent without override_kind is valid (vague chain reference)."""
    parent_id = uuid4()
    cmd = _good_command(parent_id=parent_id)
    events = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=_actor(), parent=_existing_decision()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].override_kind is None


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
def test_decide_raises_when_parent_id_set_but_context_missing() -> None:
    """Defensive: if handler skipped its load, decider raises."""
    parent_id = uuid4()
    cmd = _good_command(parent_id=parent_id)
    with pytest.raises(ParentDecisionNotFoundError):
        register_decision.decide(
            state=None,
            command=cmd,
            context=DecisionRegistrationContext(actor=_actor(), parent=None),
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Strict-not-idempotent ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing = _existing_decision()
    with pytest.raises(DecisionAlreadyExistsError) as exc_info:
        register_decision.decide(
            state=existing,
            command=_good_command(),
            context=DecisionRegistrationContext(actor=_actor()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.decision_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    actor = _actor()
    first = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=actor),
        now=_NOW,
        new_id=new_id,
    )
    second = register_decision.decide(
        state=None,
        command=cmd,
        context=DecisionRegistrationContext(actor=actor),
        now=_NOW,
        new_id=new_id,
    )
    assert first == second
