"""Unit tests for the `rotate_seal_online_key` slice's pure decider.

Live -> Live mid-lifecycle transition that swaps `online_key_ref` to a
fresh Credential. Strict-not-idempotent: rotating to the same ref the
slot already holds raises `SealCannotRotateError` (no-op rejected);
rotating against a Republishing Seal raises `SealCannotRotateError`;
rotating to a ref equal to `offline_key_ref` raises
`SealKeyCollisionError` via the `_key_separation` helper called against
the prospective post-transition state.

`rotated_by_actor_id` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`SealOnlineKeyRotated` event as the audit denorm.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotRotateError,
    SealKeyCollisionError,
    SealNotFoundError,
    SealOnlineKeyRotated,
    SealStatus,
)
from cora.federation.features import rotate_seal_online_key
from cora.federation.features.rotate_seal_online_key import RotateSealOnlineKey

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed101")
_OTHER_ACTOR_ID = UUID("01900000-0000-7000-8000-000000fed102")
_INITIALIZED_BY = UUID("01900000-0000-7000-8000-000000fed199")
_CURRENT_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_NEW_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a2")


def _seal(
    status: SealStatus,
    *,
    online_key_ref: UUID = _CURRENT_ONLINE_KEY,
    offline_key_ref: UUID = _OFFLINE_KEY,
    current_head_hash: str | None = None,
    current_sequence_number: int = 0,
) -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_key_ref=online_key_ref,
        offline_key_ref=offline_key_ref,
        current_head_hash=current_head_hash,
        current_sequence_number=current_sequence_number,
        initialized_by_actor_id=_INITIALIZED_BY,
        status=status,
    )


def _command(new_online_key_ref: UUID = _NEW_ONLINE_KEY) -> RotateSealOnlineKey:
    return RotateSealOnlineKey(
        facility_id=_FACILITY_ID,
        new_online_key_ref=new_online_key_ref,
    )


@pytest.mark.unit
def test_rotate_seal_online_key_emits_event_from_live() -> None:
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotated_by_actor_id=_PRINCIPAL_ID,
    )
    assert events == [
        SealOnlineKeyRotated(
            facility_id=_FACILITY_ID,
            new_online_key_ref=_NEW_ONLINE_KEY,
            rotated_by_actor_id=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_rotate_seal_online_key_raises_not_found_when_state_is_none() -> None:
    with pytest.raises(SealNotFoundError) as exc_info:
        rotate_seal_online_key.decide(
            state=None,
            command=_command(),
            now=_NOW,
            rotated_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc_info.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_rotate_seal_online_key_raises_cannot_rotate_when_republishing() -> None:
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(SealCannotRotateError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.current_status is SealStatus.REPUBLISHING


@pytest.mark.unit
def test_rotate_seal_online_key_raises_cannot_rotate_when_ref_equals_current_online() -> None:
    """No-op rotation rejected: rotating to the same ref the slot already holds."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(SealCannotRotateError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(new_online_key_ref=_CURRENT_ONLINE_KEY),
            now=_NOW,
            rotated_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc_info.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_rotate_seal_online_key_raises_collision_when_new_ref_equals_offline() -> None:
    """Key-separation invariant: rotating to a ref equal to offline raises."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(SealKeyCollisionError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(new_online_key_ref=_OFFLINE_KEY),
            now=_NOW,
            rotated_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.shared_key_ref == _OFFLINE_KEY


@pytest.mark.unit
def test_rotate_seal_online_key_captures_handler_injected_rotated_by_actor_id() -> None:
    """`rotated_by_actor_id` is captured verbatim from the handler, not recomputed."""
    arbitrary_principal = uuid4()
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=_NOW,
        rotated_by_actor_id=arbitrary_principal,
    )
    assert events[0].rotated_by_actor_id == arbitrary_principal


@pytest.mark.unit
def test_rotate_seal_online_key_uses_supplied_now_for_occurred_at() -> None:
    """Non-determinism injected from handler per project_non_determinism_principle."""
    custom_now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=custom_now,
        rotated_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_rotate_seal_online_key_is_pure_same_inputs_same_outputs() -> None:
    state = _seal(SealStatus.LIVE)
    command = _command()
    first = rotate_seal_online_key.decide(
        state=state, command=command, now=_NOW, rotated_by_actor_id=_PRINCIPAL_ID
    )
    second = rotate_seal_online_key.decide(
        state=state, command=command, now=_NOW, rotated_by_actor_id=_PRINCIPAL_ID
    )
    assert first == second


@pytest.mark.unit
def test_rotate_seal_online_key_actor_id_independent_of_initialized_by() -> None:
    """The rotating actor need NOT be the genesis-initializing actor; the emitted
    event records whichever id the handler injects."""
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=_NOW,
        rotated_by_actor_id=_OTHER_ACTOR_ID,
    )
    assert events[0].rotated_by_actor_id == _OTHER_ACTOR_ID


@pytest.mark.unit
def test_rotate_seal_online_key_preserves_offline_ref_on_emitted_event() -> None:
    """The offline_key_ref is NOT carried on the emitted event payload; only
    the new online ref + actor + facility ride on SealOnlineKeyRotated."""
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotated_by_actor_id=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.new_online_key_ref == _NEW_ONLINE_KEY
    assert not hasattr(event, "offline_key_ref")


@pytest.mark.unit
def test_rotate_seal_online_key_emits_event_with_state_facility_id() -> None:
    """The emitted facility_id comes from state, not the command (defensive
    against caller-side facility mismatch; state is the canonical source)."""
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotated_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].facility_id == state.facility_id


@pytest.mark.unit
def test_rotate_seal_online_key_emits_single_event() -> None:
    """One domain event per successful rotation."""
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=_NOW,
        rotated_by_actor_id=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert isinstance(events[0], SealOnlineKeyRotated)
