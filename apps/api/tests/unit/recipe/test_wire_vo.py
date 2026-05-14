"""Unit tests for the Wire value object (Phase 6h).

Pins:
  - port-name length validation (1-100 after trim)
  - canonicalization (trim leading/trailing whitespace)
  - frozenset deduplication on the 4-tuple identity
  - hashability (Wire IS hashable as a frozen dataclass)
"""

from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.plan import (
    WIRE_PORT_NAME_MAX_LENGTH,
    InvalidWireError,
    Wire,
)


def _ids() -> tuple[UUID, UUID]:
    return uuid4(), uuid4()


@pytest.mark.unit
def test_wire_constructs_with_valid_inputs() -> None:
    src, tgt = _ids()
    wire = Wire(
        source_asset_id=src,
        source_port_name="trigger_out",
        target_asset_id=tgt,
        target_port_name="trigger_in",
    )
    assert wire.source_port_name == "trigger_out"
    assert wire.target_port_name == "trigger_in"


@pytest.mark.unit
def test_wire_canonicalizes_port_names_via_trim() -> None:
    src, tgt = _ids()
    wire = Wire(
        source_asset_id=src,
        source_port_name="  trigger_out  ",
        target_asset_id=tgt,
        target_port_name="\ttrigger_in\n",
    )
    assert wire.source_port_name == "trigger_out"
    assert wire.target_port_name == "trigger_in"


@pytest.mark.unit
def test_wire_rejects_empty_source_port_name() -> None:
    src, tgt = _ids()
    with pytest.raises(InvalidWireError):
        Wire(
            source_asset_id=src,
            source_port_name="",
            target_asset_id=tgt,
            target_port_name="trigger_in",
        )


@pytest.mark.unit
def test_wire_rejects_whitespace_only_source_port_name() -> None:
    src, tgt = _ids()
    with pytest.raises(InvalidWireError):
        Wire(
            source_asset_id=src,
            source_port_name="   ",
            target_asset_id=tgt,
            target_port_name="trigger_in",
        )


@pytest.mark.unit
def test_wire_rejects_empty_target_port_name() -> None:
    src, tgt = _ids()
    with pytest.raises(InvalidWireError):
        Wire(
            source_asset_id=src,
            source_port_name="trigger_out",
            target_asset_id=tgt,
            target_port_name="",
        )


@pytest.mark.unit
def test_wire_rejects_overlong_source_port_name() -> None:
    src, tgt = _ids()
    overlong = "x" * (WIRE_PORT_NAME_MAX_LENGTH + 1)
    with pytest.raises(InvalidWireError):
        Wire(
            source_asset_id=src,
            source_port_name=overlong,
            target_asset_id=tgt,
            target_port_name="trigger_in",
        )


@pytest.mark.unit
def test_wire_accepts_max_length_port_name() -> None:
    src, tgt = _ids()
    at_max = "x" * WIRE_PORT_NAME_MAX_LENGTH
    wire = Wire(
        source_asset_id=src,
        source_port_name=at_max,
        target_asset_id=tgt,
        target_port_name="trigger_in",
    )
    assert wire.source_port_name == at_max


@pytest.mark.unit
def test_wire_is_hashable_and_dedupes_in_frozenset() -> None:
    """Two Wires with the same 4-tuple are equal AND collapse in a set."""
    src, tgt = _ids()
    w1 = Wire(
        source_asset_id=src,
        source_port_name="trigger_out",
        target_asset_id=tgt,
        target_port_name="trigger_in",
    )
    w2 = Wire(
        source_asset_id=src,
        source_port_name="trigger_out",
        target_asset_id=tgt,
        target_port_name="trigger_in",
    )
    assert w1 == w2
    assert hash(w1) == hash(w2)
    assert len(frozenset({w1, w2})) == 1


@pytest.mark.unit
def test_wire_canonicalized_names_make_equality_robust_to_whitespace() -> None:
    """Two Wires with the same logical name (mod whitespace) are equal."""
    src, tgt = _ids()
    trimmed = Wire(
        source_asset_id=src,
        source_port_name="trigger_out",
        target_asset_id=tgt,
        target_port_name="trigger_in",
    )
    padded = Wire(
        source_asset_id=src,
        source_port_name="  trigger_out  ",
        target_asset_id=tgt,
        target_port_name="\ttrigger_in\t",
    )
    assert trimmed == padded
