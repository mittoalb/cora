"""Unit tests for the `initialize_seal` slice's pure decider.

Pin the singleton-genesis guard, key-separation invariant via the
shared helper, facility_id trim-before-capture, the genesis defaults
(current_head_hash=None, current_sequence_number=0 land via the
evolver not the event), purity (same inputs -> same outputs), and
handler-injected `now` / `initialized_by_actor_id` capture per the
non-determinism principle.

Cross-aggregate purpose binding is deferred per the
[[project_federation_port_design]] eventual-consistency carve-out;
this slice does NOT raise SealKeyPurposeMismatchError today.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import (
    Seal,
    SealAlreadyExistsError,
    SealKeyCollisionError,
    SealStatus,
)
from cora.federation.features import initialize_seal
from cora.federation.features.initialize_seal import InitializeSeal

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed101")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed102")
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b1")


def _command(**overrides: object) -> InitializeSeal:
    base: dict[str, object] = {
        "facility_id": "aps-2bm",
        "online_key_ref": _ONLINE_KEY_REF,
        "offline_key_ref": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return InitializeSeal(**base)  # type: ignore[arg-type]


def _existing_state() -> Seal:
    return Seal(
        facility_id="aps-2bm",
        online_key_ref=_ONLINE_KEY_REF,
        offline_key_ref=_OFFLINE_KEY_REF,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by_actor_id=_PRINCIPAL_ID,
        status=SealStatus.LIVE,
    )


@pytest.mark.unit
def test_initialize_seal_emits_event_for_valid_command() -> None:
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == "aps-2bm"
    assert event.online_key_ref == _ONLINE_KEY_REF
    assert event.offline_key_ref == _OFFLINE_KEY_REF
    assert event.initialized_by_actor_id == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_initialize_seal_trims_facility_id_before_capture() -> None:
    events = initialize_seal.decide(
        state=None,
        command=_command(facility_id="  aps-2bm  "),
        now=_NOW,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].facility_id == "aps-2bm"


@pytest.mark.unit
def test_initialize_seal_raises_already_exists_when_state_present() -> None:
    """Singleton guard: a non-None Seal state surfaces SealAlreadyExistsError."""
    with pytest.raises(SealAlreadyExistsError) as exc:
        initialize_seal.decide(
            state=_existing_state(),
            command=_command(),
            now=_NOW,
            initialized_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == "aps-2bm"


@pytest.mark.unit
def test_initialize_seal_rejects_empty_facility_id() -> None:
    with pytest.raises(ValueError, match="Invalid facility_id"):
        initialize_seal.decide(
            state=None,
            command=_command(facility_id=""),
            now=_NOW,
            initialized_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_initialize_seal_rejects_whitespace_only_facility_id() -> None:
    with pytest.raises(ValueError, match="Invalid facility_id"):
        initialize_seal.decide(
            state=None,
            command=_command(facility_id="   "),
            now=_NOW,
            initialized_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_initialize_seal_raises_collision_when_keys_equal() -> None:
    """Key-separation invariant: online_key_ref == offline_key_ref rejects
    via the shared `verify_key_separation` helper per sec-4 AH#15."""
    shared = uuid4()
    with pytest.raises(SealKeyCollisionError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(online_key_ref=shared, offline_key_ref=shared),
            now=_NOW,
            initialized_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == "aps-2bm"
    assert exc.value.shared_key_ref == shared


@pytest.mark.unit
def test_initialize_seal_raises_collision_after_facility_id_trim() -> None:
    """Trim happens before key-separation; the collision error still
    carries the trimmed facility_id."""
    shared = uuid4()
    with pytest.raises(SealKeyCollisionError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(
                facility_id="  aps-2bm  ",
                online_key_ref=shared,
                offline_key_ref=shared,
            ),
            now=_NOW,
            initialized_by_actor_id=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == "aps-2bm"


@pytest.mark.unit
def test_initialize_seal_accepts_distinct_keys() -> None:
    """Happy path: distinct refs sail through the key-separation check."""
    events = initialize_seal.decide(
        state=None,
        command=_command(
            online_key_ref=UUID("01900000-0000-7000-8000-00000000aaa1"),
            offline_key_ref=UUID("01900000-0000-7000-8000-00000000bbb2"),
        ),
        now=_NOW,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].online_key_ref != events[0].offline_key_ref


@pytest.mark.unit
def test_initialize_seal_is_pure_same_inputs_same_outputs() -> None:
    first = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    second = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_initialize_seal_uses_handler_injected_actor_id_verbatim() -> None:
    injected = uuid4()
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by_actor_id=injected,
    )
    assert events[0].initialized_by_actor_id == injected


@pytest.mark.unit
def test_initialize_seal_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=custom_now,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_initialize_seal_records_distinct_principals_independently() -> None:
    """Two calls with different injected actor ids capture each one
    verbatim on the emitted event."""
    first = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by_actor_id=_PRINCIPAL_ID,
    )
    second = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by_actor_id=_OTHER_PRINCIPAL_ID,
    )
    assert first[0].initialized_by_actor_id == _PRINCIPAL_ID
    assert second[0].initialized_by_actor_id == _OTHER_PRINCIPAL_ID
