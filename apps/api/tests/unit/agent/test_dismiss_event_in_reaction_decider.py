"""Unit tests for the `dismiss_event_in_reaction` decider.

Validation cascade pinned in order (fail-fast):
  1. InvalidDismissalReasonError on empty / whitespace-only reason
  2. InvalidDismissalReasonError on oversize reason
  3. EventAlreadyDismissedError when event cursor <= bookmark cursor
  4. happy path: emits DecisionRegistered with the expected payload

The lexicographic-cursor check is exercised at three boundaries:
  - event same tx as bookmark, earlier position
  - event same tx as bookmark, same position
  - event same tx as bookmark, later position (allowed)
  - event earlier tx (rejected)
  - event later tx (allowed)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.errors import (
    EventAlreadyDismissedError,
    InvalidDismissalReasonError,
)
from cora.agent.features.dismiss_event_in_reaction import (
    DismissalContext,
    DismissEventInReaction,
    decide,
)
from cora.decision.aggregates.decision.state import (
    DECISION_CONTEXT_REACTION_DISMISSAL,
)

_NOW = datetime(2026, 6, 2, 14, 30, 0, tzinfo=UTC)
_EVENT_AT = datetime(2026, 6, 2, 14, 25, 0, tzinfo=UTC)
_DECISION_ID = UUID("01900000-0000-7000-8000-0000000d1551")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000007007")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee01")


def _context(
    *,
    bookmark_tx: int = 100,
    bookmark_pos: int = 50,
    event_tx: int = 100,
    event_pos: int = 51,
) -> DismissalContext:
    return DismissalContext(
        bookmark_transaction_id=bookmark_tx,
        bookmark_position=bookmark_pos,
        event_transaction_id=event_tx,
        event_position=event_pos,
        event_type="RunCompleted",
        event_recorded_at=_EVENT_AT,
    )


def _command(*, reason: str = "stuck on schema rename") -> DismissEventInReaction:
    return DismissEventInReaction(
        subscriber_name="run_debriefer",
        event_id=_EVENT_ID,
        reason=reason,
    )


def test_empty_reason_raises_invalid_dismissal_reason() -> None:
    with pytest.raises(InvalidDismissalReasonError):
        decide(
            None,
            _command(reason=""),
            context=_context(),
            new_decision_id=_DECISION_ID,
            principal_id=_PRINCIPAL_ID,
            now=_NOW,
        )


def test_whitespace_only_reason_raises_invalid_dismissal_reason() -> None:
    with pytest.raises(InvalidDismissalReasonError):
        decide(
            None,
            _command(reason="   \n\t  "),
            context=_context(),
            new_decision_id=_DECISION_ID,
            principal_id=_PRINCIPAL_ID,
            now=_NOW,
        )


def test_oversize_reason_raises_invalid_dismissal_reason() -> None:
    with pytest.raises(InvalidDismissalReasonError):
        decide(
            None,
            _command(reason="x" * 501),
            context=_context(),
            new_decision_id=_DECISION_ID,
            principal_id=_PRINCIPAL_ID,
            now=_NOW,
        )


def test_event_at_bookmark_cursor_raises_already_dismissed() -> None:
    """Event cursor == bookmark cursor: bookmark is already there;
    advancing to it is a no-op (the worker would re-deliver the SAME
    event), which is dishonest semantics for an operator action."""
    with pytest.raises(EventAlreadyDismissedError):
        decide(
            None,
            _command(),
            context=_context(bookmark_tx=100, bookmark_pos=50, event_tx=100, event_pos=50),
            new_decision_id=_DECISION_ID,
            principal_id=_PRINCIPAL_ID,
            now=_NOW,
        )


def test_event_behind_bookmark_same_tx_raises_already_dismissed() -> None:
    with pytest.raises(EventAlreadyDismissedError):
        decide(
            None,
            _command(),
            context=_context(bookmark_tx=100, bookmark_pos=50, event_tx=100, event_pos=49),
            new_decision_id=_DECISION_ID,
            principal_id=_PRINCIPAL_ID,
            now=_NOW,
        )


def test_event_behind_bookmark_earlier_tx_raises_already_dismissed() -> None:
    with pytest.raises(EventAlreadyDismissedError):
        decide(
            None,
            _command(),
            context=_context(bookmark_tx=100, bookmark_pos=50, event_tx=99, event_pos=999),
            new_decision_id=_DECISION_ID,
            principal_id=_PRINCIPAL_ID,
            now=_NOW,
        )


def test_event_ahead_same_tx_emits_decision() -> None:
    event = decide(
        None,
        _command(),
        context=_context(bookmark_tx=100, bookmark_pos=50, event_tx=100, event_pos=51),
        new_decision_id=_DECISION_ID,
        principal_id=_PRINCIPAL_ID,
        now=_NOW,
    )

    assert event.decision_id == _DECISION_ID
    assert event.actor_id == _PRINCIPAL_ID
    assert event.context == DECISION_CONTEXT_REACTION_DISMISSAL
    assert event.choice == "EventDismissed"
    assert event.occurred_at == _NOW


def test_event_ahead_later_tx_emits_decision() -> None:
    event = decide(
        None,
        _command(),
        context=_context(bookmark_tx=100, bookmark_pos=50, event_tx=101, event_pos=1),
        new_decision_id=_DECISION_ID,
        principal_id=_PRINCIPAL_ID,
        now=_NOW,
    )

    assert event.choice == "EventDismissed"
    assert event.occurred_at == _NOW


def test_happy_path_payload_carries_audit_fields() -> None:
    """The Decision's `inputs` carries every cursor the operator
    needs to reconstruct the dismissal context after the fact."""
    event = decide(
        None,
        _command(reason="schema drift after rename"),
        context=_context(bookmark_tx=42, bookmark_pos=7, event_tx=42, event_pos=8),
        new_decision_id=_DECISION_ID,
        principal_id=_PRINCIPAL_ID,
        now=_NOW,
    )

    assert event.inputs is not None
    assert event.inputs["subscriber_name"] == "run_debriefer"
    assert event.inputs["event_id"] == str(_EVENT_ID)
    assert event.inputs["event_type"] == "RunCompleted"
    assert event.inputs["event_transaction_id"] == "42"
    assert event.inputs["event_position"] == "8"
    assert event.inputs["previous_bookmark_transaction_id"] == "42"
    assert event.inputs["previous_bookmark_position"] == "7"
    assert event.reasoning is not None
    assert "schema drift after rename" in event.reasoning
    assert str(_EVENT_ID) in event.reasoning


def test_reason_is_stripped_before_emission() -> None:
    event = decide(
        None,
        _command(reason="   stripped reason   "),
        context=_context(),
        new_decision_id=_DECISION_ID,
        principal_id=_PRINCIPAL_ID,
        now=_NOW,
    )
    assert event.reasoning is not None
    assert "stripped reason" in event.reasoning
    assert "   stripped reason   " not in event.reasoning


def test_decider_is_pure_no_side_effect_on_inputs() -> None:
    """Pass the same inputs twice, assert identical outputs. Pins
    the decider's purity claim (no hidden state, no clock reads)."""
    ctx = _context()
    cmd = _command()
    first = decide(
        None,
        cmd,
        context=ctx,
        new_decision_id=_DECISION_ID,
        principal_id=_PRINCIPAL_ID,
        now=_NOW,
    )
    second = decide(
        None,
        cmd,
        context=ctx,
        new_decision_id=_DECISION_ID,
        principal_id=_PRINCIPAL_ID,
        now=_NOW,
    )
    assert first == second


# Suppress unused-id warning since we exercise the structural-typing
# UUID for completeness across cases.
_ = uuid4
