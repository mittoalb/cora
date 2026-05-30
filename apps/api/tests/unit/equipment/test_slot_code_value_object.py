"""Unit tests for the SlotCode value object (Mount's external alias).

Mirrors the bounded-text-VO test shape: empty / whitespace-only /
overlong rejection + `.value` attribute pin + trim behaviour +
frozen-dataclass invariants.
"""

from dataclasses import FrozenInstanceError

import pytest

from cora.equipment.aggregates.mount import (
    SLOT_CODE_MAX_LENGTH,
    InvalidSlotCodeError,
    SlotCode,
)


@pytest.mark.unit
def test_slot_code_constructs_with_valid_input() -> None:
    code = SlotCode("02-BM-A-K-01")
    assert code.value == "02-BM-A-K-01"


@pytest.mark.unit
def test_slot_code_trims_whitespace() -> None:
    code = SlotCode("  02-BM-A-K-01  ")
    assert code.value == "02-BM-A-K-01"


@pytest.mark.unit
def test_slot_code_rejects_empty_string() -> None:
    with pytest.raises(InvalidSlotCodeError) as info:
        SlotCode("")
    assert info.value.value == ""
    assert "slot_code" in str(info.value)


@pytest.mark.unit
def test_slot_code_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidSlotCodeError) as info:
        SlotCode("   ")
    assert info.value.value == "   "


@pytest.mark.unit
def test_slot_code_rejects_oversized() -> None:
    overlong = "x" * (SLOT_CODE_MAX_LENGTH + 1)
    with pytest.raises(InvalidSlotCodeError) as info:
        SlotCode(overlong)
    assert info.value.value == overlong


@pytest.mark.unit
def test_slot_code_accepts_max_length() -> None:
    """Boundary check: exactly MAX_LENGTH is accepted; only MAX+1 rejects."""
    code = SlotCode("x" * SLOT_CODE_MAX_LENGTH)
    assert len(code.value) == SLOT_CODE_MAX_LENGTH


@pytest.mark.unit
def test_slot_code_is_frozen() -> None:
    code = SlotCode("02-BM-A-K-01")
    with pytest.raises(FrozenInstanceError):
        code.value = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_slot_code_equality_is_structural_after_trim() -> None:
    a = SlotCode("02-BM-A-K-01")
    b = SlotCode("  02-BM-A-K-01 ")
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_invalid_slot_code_error_carries_value() -> None:
    err = InvalidSlotCodeError("  ")
    assert err.value == "  "
    assert "slot_code" in str(err)
