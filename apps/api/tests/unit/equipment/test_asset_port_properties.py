"""Property-based tests for the AssetPort value object.

Complements `test_asset_port_value_object.py` (example-based) with
universal claims over the generated input space:

  - For any valid (name, direction, signal_type), construction
    succeeds and round-trips.
  - For any padded name/signal_type, the canonical (trimmed)
    AssetPort equals the unpadded version.
  - For any overlong name or signal_type, construction raises the
    correct error variant.
  - Equal-by-tuple AssetPorts share a hash (frozenset dedup).
"""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset.state import (
    PORT_NAME_MAX_LENGTH,
    PORT_SIGNAL_TYPE_MAX_LENGTH,
    AssetPort,
    InvalidAssetPortNameError,
    InvalidAssetPortSignalTypeError,
    PortDirection,
)

_NAME_BODY = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=PORT_NAME_MAX_LENGTH,
)
_SIGNAL_BODY = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=PORT_SIGNAL_TYPE_MAX_LENGTH,
)
_DIRECTION = st.sampled_from(list(PortDirection))


@pytest.mark.unit
@given(name=_NAME_BODY, direction=_DIRECTION, signal=_SIGNAL_BODY)
def test_asset_port_constructs_for_any_valid_triple(
    name: str, direction: PortDirection, signal: str
) -> None:
    """Any valid triple builds and round-trips its fields."""
    port = AssetPort(name=name, direction=direction, signal_type=signal)
    assert port.name == name
    assert port.direction is direction
    assert port.signal_type == signal


_WS_PAD = st.text(alphabet=" \t\n\r", min_size=1, max_size=5)


@pytest.mark.unit
@given(
    name=_NAME_BODY,
    direction=_DIRECTION,
    signal=_SIGNAL_BODY,
    pad_l=_WS_PAD,
    pad_r=_WS_PAD,
)
def test_asset_port_canonicalises_whitespace_padding(
    name: str,
    direction: PortDirection,
    signal: str,
    pad_l: str,
    pad_r: str,
) -> None:
    """A padded port equals the unpadded one after trim."""
    assume(name == name.strip() and signal == signal.strip())
    padded = AssetPort(
        name=pad_l + name + pad_r,
        direction=direction,
        signal_type=pad_l + signal + pad_r,
    )
    unpadded = AssetPort(name=name, direction=direction, signal_type=signal)
    assert padded == unpadded
    assert hash(padded) == hash(unpadded)


@pytest.mark.unit
@given(
    overlong_name=st.text(
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
        min_size=PORT_NAME_MAX_LENGTH + 1,
        max_size=PORT_NAME_MAX_LENGTH + 50,
    ),
    direction=_DIRECTION,
)
def test_asset_port_rejects_overlong_name(overlong_name: str, direction: PortDirection) -> None:
    """Any name beyond the cap raises the name-specific error."""
    with pytest.raises(InvalidAssetPortNameError):
        AssetPort(name=overlong_name, direction=direction, signal_type="TTL")


@pytest.mark.unit
@given(
    name=_NAME_BODY,
    direction=_DIRECTION,
    overlong_signal=st.text(
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
        min_size=PORT_SIGNAL_TYPE_MAX_LENGTH + 1,
        max_size=PORT_SIGNAL_TYPE_MAX_LENGTH + 50,
    ),
)
def test_asset_port_rejects_overlong_signal_type(
    name: str, direction: PortDirection, overlong_signal: str
) -> None:
    """Any signal_type beyond the cap raises the signal-specific error."""
    with pytest.raises(InvalidAssetPortSignalTypeError):
        AssetPort(name=name, direction=direction, signal_type=overlong_signal)


@pytest.mark.unit
@given(name=_NAME_BODY, direction=_DIRECTION, signal=_SIGNAL_BODY)
def test_equal_asset_ports_collapse_in_a_frozenset(
    name: str, direction: PortDirection, signal: str
) -> None:
    p1 = AssetPort(name=name, direction=direction, signal_type=signal)
    p2 = AssetPort(name=name, direction=direction, signal_type=signal)
    assert frozenset({p1, p2}) == frozenset({p1})
