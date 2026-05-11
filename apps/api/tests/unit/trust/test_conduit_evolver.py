"""Unit tests for the Conduit aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.channel import ChannelFieldSpec, ChannelSchema
from cora.trust.aggregates.conduit import (
    Conduit,
    ConduitChannelAlreadyOpenError,
    ConduitChannelNotOpenError,
    ConduitName,
    evolve,
    fold,
)
from cora.trust.aggregates.conduit.events import (
    ConduitChannelClosed,
    ConduitChannelOpened,
    ConduitDefined,
)
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit


def _sample_schema() -> ChannelSchema:
    return ChannelSchema(fields={"x": ChannelFieldSpec(type="string")})


_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_conduit_defined_from_empty_state() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    state = evolve(
        None,
        ConduitDefined(
            conduit_id=conduit_id,
            name="Detector-to-Storage",
            source_zone_id=source,
            target_zone_id=target,
            occurred_at=_NOW,
        ),
    )
    assert state == Conduit(
        id=conduit_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_conduit_defined_returns_conduit() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    state = fold(
        [
            ConduitDefined(
                conduit_id=conduit_id,
                name="Detector-to-Storage",
                source_zone_id=source,
                target_zone_id=target,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Conduit(
        id=conduit_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    conduit_id = uuid4()
    events = [
        ConduitDefined(
            conduit_id=conduit_id,
            name="Detector-to-Storage",
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state.

    Phase 6f-5a: the decider emits ConduitDefined + ConduitChannelOpened,
    and the evolver folds both into a Conduit with the traversals
    channel id present in `open_channels`.
    """
    new_id = uuid4()
    channel_id = uuid4()
    source = uuid4()
    target = uuid4()
    command = DefineConduit(
        name="  Detector-to-Storage  ",  # whitespace exercises the VO trim
        source_zone_id=source,
        target_zone_id=target,
    )

    events = define_conduit.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        traversals_channel_id=channel_id,
    )
    rebuilt = fold(events)

    assert rebuilt == Conduit(
        id=new_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
        open_channels=frozenset({channel_id}),
    )


# ---------- Channel-event arms (Phase 6f-5a) ----------


def _genesis(conduit_id: object | None = None) -> ConduitDefined:
    return ConduitDefined(
        conduit_id=conduit_id or uuid4(),  # type: ignore[arg-type]
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_channel_opened_adds_id_to_open_channels() -> None:
    genesis = _genesis()
    state = evolve(None, genesis)
    channel_id = uuid4()
    after_open = evolve(
        state,
        ConduitChannelOpened(
            conduit_id=genesis.conduit_id,
            channel_id=channel_id,
            kind="traversals",
            schema=_sample_schema(),
            occurred_at=_NOW,
        ),
    )
    assert after_open.open_channels == frozenset({channel_id})


@pytest.mark.unit
def test_evolve_channel_closed_removes_id_from_open_channels() -> None:
    genesis = _genesis()
    state = evolve(None, genesis)
    channel_id = uuid4()
    state = evolve(
        state,
        ConduitChannelOpened(
            conduit_id=genesis.conduit_id,
            channel_id=channel_id,
            kind="traversals",
            schema=_sample_schema(),
            occurred_at=_NOW,
        ),
    )
    state = evolve(
        state,
        ConduitChannelClosed(
            conduit_id=genesis.conduit_id,
            channel_id=channel_id,
            occurred_at=_NOW,
        ),
    )
    assert state.open_channels == frozenset()


@pytest.mark.unit
def test_evolve_channel_opened_on_none_state_raises() -> None:
    """Defensive guard: a channel-open before genesis is stream
    contamination — fail loud."""
    with pytest.raises(ValueError, match="ConduitChannelOpened before ConduitDefined"):
        evolve(
            None,
            ConduitChannelOpened(
                conduit_id=uuid4(),
                channel_id=uuid4(),
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolve_channel_closed_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="ConduitChannelClosed before ConduitDefined"):
        evolve(
            None,
            ConduitChannelClosed(conduit_id=uuid4(), channel_id=uuid4(), occurred_at=_NOW),
        )


@pytest.mark.unit
def test_evolve_channel_opened_raises_when_id_already_open() -> None:
    """Defensive guard: same channel id reopened means stream
    contamination (channel ids are UUIDv7-fresh per opening)."""
    genesis = _genesis()
    channel_id = uuid4()
    open_event = ConduitChannelOpened(
        conduit_id=genesis.conduit_id,
        channel_id=channel_id,
        kind="traversals",
        schema=_sample_schema(),
        occurred_at=_NOW,
    )
    state = evolve(None, genesis)
    state = evolve(state, open_event)
    with pytest.raises(ConduitChannelAlreadyOpenError) as exc_info:
        evolve(state, open_event)
    assert exc_info.value.channel_id == channel_id


@pytest.mark.unit
def test_evolve_channel_closed_raises_when_id_not_open() -> None:
    """Defensive guard: closing a channel that's not open is stream
    contamination."""
    genesis = _genesis()
    state = evolve(None, genesis)
    unknown_channel_id = uuid4()
    with pytest.raises(ConduitChannelNotOpenError) as exc_info:
        evolve(
            state,
            ConduitChannelClosed(
                conduit_id=genesis.conduit_id,
                channel_id=unknown_channel_id,
                occurred_at=_NOW,
            ),
        )
    assert exc_info.value.channel_id == unknown_channel_id


@pytest.mark.unit
def test_fold_full_open_close_cycle_yields_empty_open_channels() -> None:
    """Channel lifecycle: open then close brings open_channels back
    to empty, like a stack."""
    genesis = _genesis()
    channel_id = uuid4()
    state = fold(
        [
            genesis,
            ConduitChannelOpened(
                conduit_id=genesis.conduit_id,
                channel_id=channel_id,
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
            ConduitChannelClosed(
                conduit_id=genesis.conduit_id,
                channel_id=channel_id,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.open_channels == frozenset()


@pytest.mark.unit
def test_fold_supports_multiple_open_channels_simultaneously() -> None:
    """The aggregate state allows multiple channels open at once;
    today only `traversals` ships, but the slot-set design supports
    future per-kind channels (frame_triggers, motor_positions, ...)."""
    genesis = _genesis()
    ch_a = uuid4()
    ch_b = uuid4()
    state = fold(
        [
            genesis,
            ConduitChannelOpened(
                conduit_id=genesis.conduit_id,
                channel_id=ch_a,
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
            ConduitChannelOpened(
                conduit_id=genesis.conduit_id,
                channel_id=ch_b,
                kind="other_kind",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.open_channels == frozenset({ch_a, ch_b})
