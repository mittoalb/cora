"""Unit tests for the `start_seal_republishing` slice's pure decider.

Pin the FSM single-source guard (Live is the only legal source),
the not-found branch, purity (same inputs -> same outputs), and the
handler-injected `started_by_actor_id` / `now` capture per the
non-determinism principle (capture, don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealRepublishingStarted,
    SealStatus,
)
from cora.federation.features import start_seal_republishing
from cora.federation.features.start_seal_republishing import (
    StartSealRepublishing,
)

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fec001")
_INITIALIZED_BY = UUID("01900000-0000-7000-8000-000000fec099")
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-000000fec0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-000000fec0b1")


def _seal(status: SealStatus) -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_key_ref=_ONLINE_KEY_REF,
        offline_key_ref=_OFFLINE_KEY_REF,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by_actor_id=_INITIALIZED_BY,
        status=status,
    )


def _command(*, reason: str | None = "root rotation drill") -> StartSealRepublishing:
    return StartSealRepublishing(facility_id=_FACILITY_ID, reason=reason)


@pytest.mark.unit
def test_start_seal_republishing_emits_event_when_state_is_live() -> None:
    state = _seal(SealStatus.LIVE)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by_actor_id=_PRINCIPAL_ID,
    )
    assert events == [
        SealRepublishingStarted(
            facility_id=_FACILITY_ID,
            started_by_actor_id=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_start_seal_republishing_raises_not_found_when_state_is_none() -> None:
    with pytest.raises(SealNotFoundError):
        start_seal_republishing.decide(
            state=None,
            command=_command(),
            now=_NOW,
            started_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_start_seal_republishing_raises_cannot_start_when_already_republishing() -> None:
    """Single-source: starting against an already-Republishing Seal rejects."""
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(SealCannotStartRepublishingError) as exc:
        start_seal_republishing.decide(
            state=state,
            command=_command(),
            now=_NOW,
            started_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc.value.current_status is SealStatus.REPUBLISHING
    assert exc.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_start_seal_republishing_accepts_none_reason() -> None:
    """Reason is optional on the command; absent reason still emits the event."""
    state = _seal(SealStatus.LIVE)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(reason=None),
        now=_NOW,
        started_by_actor_id=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].facility_id == _FACILITY_ID


@pytest.mark.unit
def test_start_seal_republishing_is_pure_same_inputs_same_outputs() -> None:
    state = _seal(SealStatus.LIVE)
    first = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by_actor_id=_PRINCIPAL_ID,
    )
    second = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by_actor_id=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_start_seal_republishing_uses_handler_injected_actor_id_verbatim() -> None:
    state = _seal(SealStatus.LIVE)
    injected = uuid4()
    events = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by_actor_id=injected,
    )
    assert events[0].started_by_actor_id == injected


@pytest.mark.unit
def test_start_seal_republishing_uses_handler_injected_now_verbatim() -> None:
    state = _seal(SealStatus.LIVE)
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=custom_now,
        started_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_start_seal_republishing_does_not_carry_reason_into_event() -> None:
    """Locked event payload is (facility_id, started_by_actor_id, occurred_at);
    the command-level reason is intentionally not threaded into the event."""
    state = _seal(SealStatus.LIVE)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(reason="key compromise drill"),
        now=_NOW,
        started_by_actor_id=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert not hasattr(events[0], "reason")
