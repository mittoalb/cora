"""Unit tests for DecisionRatingsProjection.

Post-cleanup: `confidence_at_rating` is captured at write time
on the DecisionRated event payload (gate-review cross-BC P2-4); the
projection no longer reads `proj_decision_summary` at apply() time.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.decision.projections.ratings import DecisionRatingsProjection
from cora.infrastructure.ports.event_store import StoredEvent

_T0 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_DECISION_ID = UUID("01900000-0000-7000-8000-00000000aa01")
_RATER_ID = UUID("01900000-0000-7000-8000-00000000aa02")


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=_DECISION_ID,
        version=2,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_T0,
        recorded_at=_T0,
    )


def _decision_rated_event(
    rating: str = "useful",
    comment: str | None = None,
    confidence: float | None = 0.85,
) -> StoredEvent:
    return _stored(
        "DecisionRated",
        {
            "decision_id": str(_DECISION_ID),
            "rating": rating,
            "comment": comment,
            "rated_by_actor_id": str(_RATER_ID),
            "rated_at": _T0.isoformat(),
            "occurred_at": _T0.isoformat(),
            "confidence_at_rating": confidence,
        },
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = DecisionRatingsProjection()
    assert proj.name == "proj_decision_ratings"
    assert proj.subscribed_event_types == frozenset({"DecisionRated"})


@pytest.mark.unit
async def test_apply_upserts_rating_with_payload_borne_confidence() -> None:
    """Apply UPSERTs the row with `confidence_at_rating` taken from
    the event payload (NOT a cross-projection lookup)."""
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _decision_rated_event(rating="useful", comment="helpful", confidence=0.85)

    await proj.apply(event, conn)

    # ONE SQL call: the UPSERT. No fetchrow (no cross-projection read).
    conn.fetchrow.assert_not_awaited()
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_decision_ratings" in sql
    assert "ON CONFLICT (decision_id, rated_by_actor_id) DO UPDATE" in sql
    # Args (positional): decision_id, rated_by_actor_id, rating, comment, rated_at, confidence
    assert args.args[1] == _DECISION_ID
    assert args.args[2] == _RATER_ID
    assert args.args[3] == "useful"
    assert args.args[4] == "helpful"
    assert args.args[5] == _T0
    assert args.args[6] == 0.85


@pytest.mark.unit
async def test_apply_null_comment_passes_through() -> None:
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _decision_rated_event(rating="ignored", comment=None)

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # comment


@pytest.mark.unit
async def test_apply_null_confidence_at_rating_passes_through() -> None:
    """When the rated Decision had no confidence value (or the event
    payload omits it for backward-compat), confidence_at_rating
    lands NULL."""
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _decision_rated_event(confidence=None)

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[6] is None  # confidence_at_rating


@pytest.mark.unit
async def test_apply_missing_confidence_field_falls_back_to_none() -> None:
    """Forward-compat: a payload missing `confidence_at_rating`
    entirely (pre-cleanup shape, not in production) lands NULL."""
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRated",
        {
            "decision_id": str(_DECISION_ID),
            "rating": "useful",
            "comment": None,
            "rated_by_actor_id": str(_RATER_ID),
            "rated_at": _T0.isoformat(),
            "occurred_at": _T0.isoformat(),
            # No "confidence_at_rating"
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[6] is None


@pytest.mark.unit
async def test_apply_ignores_non_subscribed_events() -> None:
    """Defensive: if a non-DecisionRated event reaches apply()
    (shouldn't happen because the worker SQL filter gates by
    subscribed_event_types), the apply() returns without writing."""
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _stored("DecisionRegistered", {})

    await proj.apply(event, conn)

    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_upsert_uses_latest_rated_at_predicate() -> None:
    """The ON CONFLICT WHERE clause guards against out-of-order
    replay regressing the projection state."""
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _decision_rated_event()

    await proj.apply(event, conn)

    sql = conn.execute.await_args.args[0]
    assert "WHERE EXCLUDED.rated_at > proj_decision_ratings.rated_at" in sql


@pytest.mark.unit
async def test_apply_is_idempotent_replays_produce_same_sql() -> None:
    """Re-applying the same DecisionRated event runs the same UPSERT.

    The latest-rated_at predicate short-circuits when EXCLUDED.rated_at
    equals the existing value (no overwrite); the net effect on the
    projection is a no-op. Closes gate-review test-coverage P1-4.
    """
    proj = DecisionRatingsProjection()
    conn = AsyncMock()
    event = _decision_rated_event()

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    first = conn.execute.await_args_list[0].args
    second = conn.execute.await_args_list[1].args
    assert first == second  # identical SQL + identical args
