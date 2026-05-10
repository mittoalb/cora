"""ConduitName value-object validation."""

import pytest

from cora.trust.aggregates.conduit import ConduitName, InvalidConduitNameError


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
