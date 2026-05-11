"""ConduitName value-object validation + channel-state error classes."""

from uuid import uuid4

import pytest

from cora.trust.aggregates.conduit import (
    CHANNEL_KIND_TRAVERSALS,
    ConduitChannelAlreadyOpenError,
    ConduitChannelNotOpenError,
    ConduitName,
    InvalidConduitNameError,
)


@pytest.mark.unit
def test_conduit_name_accepts_normal_string() -> None:
    name = ConduitName("Detector-to-Storage")
    assert name.value == "Detector-to-Storage"


@pytest.mark.unit
def test_conduit_name_trims_whitespace() -> None:
    name = ConduitName("  Detector-to-Storage  ")
    assert name.value == "Detector-to-Storage"


@pytest.mark.unit
def test_conduit_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidConduitNameError):
        ConduitName("")


@pytest.mark.unit
def test_conduit_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidConduitNameError):
        ConduitName("   \t\n   ")


@pytest.mark.unit
def test_conduit_name_rejects_too_long() -> None:
    with pytest.raises(InvalidConduitNameError):
        ConduitName("a" * 201)


@pytest.mark.unit
def test_conduit_name_accepts_max_length() -> None:
    name = ConduitName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_conduit_name_is_frozen() -> None:
    name = ConduitName("Detector-to-Storage")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- Channel-state error classes (Phase 6f-5a) ----------


@pytest.mark.unit
def test_channel_kind_traversals_is_a_stable_string_constant() -> None:
    """Stored on disk in event payloads — value must not change without
    an explicit migration story for old events."""
    assert CHANNEL_KIND_TRAVERSALS == "traversals"


@pytest.mark.unit
def test_conduit_channel_already_open_error_carries_ids() -> None:
    conduit_id = uuid4()
    channel_id = uuid4()
    err = ConduitChannelAlreadyOpenError(conduit_id, channel_id)
    assert err.conduit_id == conduit_id
    assert err.channel_id == channel_id
    msg = str(err)
    assert str(channel_id) in msg
    assert "open" in msg.lower()


@pytest.mark.unit
def test_conduit_channel_not_open_error_carries_ids() -> None:
    conduit_id = uuid4()
    channel_id = uuid4()
    err = ConduitChannelNotOpenError(conduit_id, channel_id)
    assert err.conduit_id == conduit_id
    assert err.channel_id == channel_id
    msg = str(err)
    assert str(channel_id) in msg
    assert "no open" in msg.lower()
