"""Unit tests for the AssetPort value object + PortDirection enum."""

import pytest

from cora.equipment.aggregates.asset import (
    AssetPort,
    InvalidAssetPortNameError,
    InvalidAssetPortSignalTypeError,
    PortDirection,
)


@pytest.mark.unit
def test_port_direction_values_are_pascalcase_strings() -> None:
    """Pinned: PortDirection serializes as 'Input' / 'Output' so the
    JSON wire format reads naturally and the route's Literal[...]
    type annotation matches."""
    assert PortDirection.INPUT.value == "Input"
    assert PortDirection.OUTPUT.value == "Output"


@pytest.mark.unit
def test_asset_port_constructs_with_valid_inputs() -> None:
    port = AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")
    assert port.name == "trigger_in"
    assert port.direction is PortDirection.INPUT
    assert port.signal_type == "TTL"


@pytest.mark.unit
def test_asset_port_trims_name_and_signal_type() -> None:
    port = AssetPort(
        name="  trigger_in  ",
        direction=PortDirection.INPUT,
        signal_type="  TTL  ",
    )
    assert port.name == "trigger_in"
    assert port.signal_type == "TTL"


@pytest.mark.unit
def test_asset_port_rejects_empty_name() -> None:
    with pytest.raises(InvalidAssetPortNameError):
        AssetPort(name="", direction=PortDirection.INPUT, signal_type="TTL")


@pytest.mark.unit
def test_asset_port_rejects_whitespace_only_name() -> None:
    with pytest.raises(InvalidAssetPortNameError):
        AssetPort(name="   ", direction=PortDirection.INPUT, signal_type="TTL")


@pytest.mark.unit
def test_asset_port_rejects_oversized_name() -> None:
    with pytest.raises(InvalidAssetPortNameError):
        AssetPort(name="x" * 101, direction=PortDirection.INPUT, signal_type="TTL")


@pytest.mark.unit
def test_asset_port_rejects_empty_signal_type() -> None:
    with pytest.raises(InvalidAssetPortSignalTypeError):
        AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="")


@pytest.mark.unit
def test_asset_port_rejects_oversized_signal_type() -> None:
    with pytest.raises(InvalidAssetPortSignalTypeError):
        AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="x" * 51)


@pytest.mark.unit
def test_asset_port_is_frozen_and_hashable() -> None:
    """Pinned: AssetPort instances are frozen dataclasses (hashable)
    so they can live in a frozenset on Asset state."""
    from dataclasses import FrozenInstanceError

    port = AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")
    # Hashable: can go into a set
    s = {port}
    assert port in s
    # Frozen: can't be mutated
    with pytest.raises(FrozenInstanceError):
        port.name = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_asset_port_equality_is_value_based() -> None:
    """Two AssetPorts with the same fields are equal regardless of
    whitespace in the source values."""
    a = AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")
    b = AssetPort(name="  trigger_in  ", direction=PortDirection.INPUT, signal_type=" TTL ")
    assert a == b


@pytest.mark.unit
def test_asset_port_with_different_direction_is_not_equal() -> None:
    a = AssetPort(name="trigger", direction=PortDirection.INPUT, signal_type="TTL")
    b = AssetPort(name="trigger", direction=PortDirection.OUTPUT, signal_type="TTL")
    assert a != b
