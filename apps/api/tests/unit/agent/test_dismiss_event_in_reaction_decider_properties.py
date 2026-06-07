"""Property-based tests for `dismiss_event_in_reaction.decide`.

Pins universal behaviour across generated inputs:

  - Empty / whitespace-only reason → InvalidDismissalReasonError, always.
  - Oversize reason (>500 chars after strip) → InvalidDismissalReasonError, always.
  - Event cursor (event_tx, event_pos) <= bookmark cursor
    (bookmark_tx, bookmark_pos) → EventAlreadyDismissedError, always
    (lexicographic comparison).
  - Event cursor strictly > bookmark cursor with a valid reason →
    a single DecisionRegistered with the correct context, choice,
    and audit payload.
  - Pure: same inputs → same output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from uuid import UUID

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


def _ctx(
    *,
    bookmark_tx: int,
    bookmark_pos: int,
    event_tx: int,
    event_pos: int,
) -> DismissalContext:
    return DismissalContext(
        bookmark_transaction_id=bookmark_tx,
        bookmark_position=bookmark_pos,
        event_transaction_id=event_tx,
        event_position=event_pos,
        event_type="ProbeEvent",
        event_recorded_at=_EVENT_AT,
    )


@pytest.mark.unit
@given(
    subscriber_name=st.text(min_size=1, max_size=50),
    event_id=st.uuids(),
    whitespace=st.text(alphabet=" \t\n", min_size=0, max_size=20),
    decision_id=st.uuids(),
    principal_id=st.uuids(),
)
def test_whitespace_only_reason_always_raises_invalid(
    subscriber_name: str,
    event_id: UUID,
    whitespace: str,
    decision_id: UUID,
    principal_id: UUID,
) -> None:
    with pytest.raises(InvalidDismissalReasonError):
        decide(
            None,
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=event_id,
                reason=whitespace,
            ),
            context=_ctx(bookmark_tx=0, bookmark_pos=0, event_tx=1, event_pos=1),
            new_decision_id=decision_id,
            principal_id=principal_id,
            now=_NOW,
        )


@pytest.mark.unit
@given(
    subscriber_name=st.text(min_size=1, max_size=50),
    event_id=st.uuids(),
    excess_chars=st.integers(min_value=1, max_value=2000),
    decision_id=st.uuids(),
    principal_id=st.uuids(),
)
def test_oversize_reason_always_raises_invalid(
    subscriber_name: str,
    event_id: UUID,
    excess_chars: int,
    decision_id: UUID,
    principal_id: UUID,
) -> None:
    """Any reason with stripped length > 500 raises."""
    reason = "x" * (500 + excess_chars)
    with pytest.raises(InvalidDismissalReasonError):
        decide(
            None,
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=event_id,
                reason=reason,
            ),
            context=_ctx(bookmark_tx=0, bookmark_pos=0, event_tx=1, event_pos=1),
            new_decision_id=decision_id,
            principal_id=principal_id,
            now=_NOW,
        )


@pytest.mark.unit
@given(
    subscriber_name=st.text(min_size=1, max_size=50),
    event_id=st.uuids(),
    reason=st.text(min_size=1, max_size=500).filter(lambda r: r.strip()),
    bookmark_tx=st.integers(min_value=1, max_value=10000),
    bookmark_pos=st.integers(min_value=1, max_value=10000),
    decision_id=st.uuids(),
    principal_id=st.uuids(),
)
def test_event_at_or_behind_bookmark_always_raises_already_dismissed(
    subscriber_name: str,
    event_id: UUID,
    reason: str,
    bookmark_tx: int,
    bookmark_pos: int,
    decision_id: UUID,
    principal_id: UUID,
) -> None:
    """Event cursor strictly <= bookmark cursor raises (no rewinds)."""
    with pytest.raises(EventAlreadyDismissedError):
        decide(
            None,
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=event_id,
                reason=reason,
            ),
            context=_ctx(
                bookmark_tx=bookmark_tx,
                bookmark_pos=bookmark_pos,
                event_tx=bookmark_tx,
                event_pos=bookmark_pos,
            ),
            new_decision_id=decision_id,
            principal_id=principal_id,
            now=_NOW,
        )


@pytest.mark.unit
@given(
    subscriber_name=st.text(min_size=1, max_size=50),
    event_id=st.uuids(),
    reason=st.text(min_size=1, max_size=500).filter(lambda r: r.strip()),
    bookmark_tx=st.integers(min_value=0, max_value=10000),
    bookmark_pos=st.integers(min_value=0, max_value=10000),
    pos_delta=st.integers(min_value=1, max_value=10000),
    decision_id=st.uuids(),
    principal_id=st.uuids(),
)
def test_event_strictly_ahead_emits_decision_with_expected_payload(
    subscriber_name: str,
    event_id: UUID,
    reason: str,
    bookmark_tx: int,
    bookmark_pos: int,
    pos_delta: int,
    decision_id: UUID,
    principal_id: UUID,
) -> None:
    """Event strictly ahead in (tx, pos) order always yields a single
    DecisionRegistered with the expected context + choice + audit
    payload."""
    event_tx = bookmark_tx
    event_pos = bookmark_pos + pos_delta

    decision = decide(
        None,
        DismissEventInReaction(
            subscriber_name=subscriber_name,
            event_id=event_id,
            reason=reason,
        ),
        context=_ctx(
            bookmark_tx=bookmark_tx,
            bookmark_pos=bookmark_pos,
            event_tx=event_tx,
            event_pos=event_pos,
        ),
        new_decision_id=decision_id,
        principal_id=principal_id,
        now=_NOW,
    )

    assert decision.decision_id == decision_id
    assert decision.decided_by == principal_id
    assert decision.context == DECISION_CONTEXT_REACTION_DISMISSAL
    assert decision.choice == "EventDismissed"
    assert decision.occurred_at == _NOW
    assert decision.inputs is not None
    assert decision.inputs["subscriber_name"] == subscriber_name
    assert decision.inputs["event_id"] == str(event_id)
    assert decision.inputs["event_transaction_id"] == str(event_tx)
    assert decision.inputs["event_position"] == str(event_pos)
    assert decision.inputs["previous_bookmark_transaction_id"] == str(bookmark_tx)
    assert decision.inputs["previous_bookmark_position"] == str(bookmark_pos)


@pytest.mark.unit
@given(
    subscriber_name=st.text(min_size=1, max_size=50),
    event_id=st.uuids(),
    reason=st.text(min_size=1, max_size=500).filter(lambda r: r.strip()),
    bookmark_tx=st.integers(min_value=0, max_value=10000),
    bookmark_pos=st.integers(min_value=0, max_value=10000),
    pos_delta=st.integers(min_value=1, max_value=10000),
    decision_id=st.uuids(),
    principal_id=st.uuids(),
)
def test_decider_is_pure_same_inputs_same_output(
    subscriber_name: str,
    event_id: UUID,
    reason: str,
    bookmark_tx: int,
    bookmark_pos: int,
    pos_delta: int,
    decision_id: UUID,
    principal_id: UUID,
) -> None:
    cmd = DismissEventInReaction(
        subscriber_name=subscriber_name,
        event_id=event_id,
        reason=reason,
    )
    ctx = _ctx(
        bookmark_tx=bookmark_tx,
        bookmark_pos=bookmark_pos,
        event_tx=bookmark_tx,
        event_pos=bookmark_pos + pos_delta,
    )

    first = decide(
        None,
        cmd,
        context=ctx,
        new_decision_id=decision_id,
        principal_id=principal_id,
        now=_NOW,
    )
    second = decide(
        None,
        cmd,
        context=ctx,
        new_decision_id=decision_id,
        principal_id=principal_id,
        now=_NOW,
    )
    assert first == second
