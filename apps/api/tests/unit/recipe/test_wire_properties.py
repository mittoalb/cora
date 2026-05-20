"""Property-based tests for the Wire value object (Phase 6h).

Complements `test_wire_vo.py` (example-based) with universal claims
across the generated input space:

  - For any valid 4-tuple, construction succeeds and round-trips.
  - For any name padded with whitespace, the constructed Wire equals
    the unpadded version (canonicalisation invariant).
  - For any name with len > WIRE_PORT_NAME_MAX_LENGTH, construction
    raises InvalidWireError.
  - Equal-by-tuple Wires share a hash (frozenset dedup invariant).

These properties catch failure modes the example tests would only
catch by accident — e.g. a tab-character that survives trim, a name
whose validation differs only at specific lengths, a hash collision
masked by the small fixed example pool.

Iter C of the testing-techniques rollout.
"""

from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.plan import (
    WIRE_PORT_NAME_MAX_LENGTH,
    InvalidWireError,
    Wire,
)

_PORT_NAME_BODY = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=WIRE_PORT_NAME_MAX_LENGTH,
)


@pytest.mark.unit
@given(
    src_id=st.uuids(),
    src_name=_PORT_NAME_BODY,
    tgt_id=st.uuids(),
    tgt_name=_PORT_NAME_BODY,
)
def test_wire_constructs_for_any_valid_tuple(
    src_id: UUID, src_name: str, tgt_id: UUID, tgt_name: str
) -> None:
    """Any 4-tuple with non-empty, non-whitespace, in-range names builds."""
    wire = Wire(
        source_asset_id=src_id,
        source_port_name=src_name,
        target_asset_id=tgt_id,
        target_port_name=tgt_name,
    )
    assert wire.source_asset_id == src_id
    assert wire.target_asset_id == tgt_id
    assert wire.source_port_name == src_name
    assert wire.target_port_name == tgt_name


_LEADING_OR_TRAILING_WS = st.text(alphabet=" \t\n\r", min_size=1, max_size=5)


@pytest.mark.unit
@given(
    src_id=st.uuids(),
    src_name=_PORT_NAME_BODY,
    tgt_id=st.uuids(),
    tgt_name=_PORT_NAME_BODY,
    pad_left=_LEADING_OR_TRAILING_WS,
    pad_right=_LEADING_OR_TRAILING_WS,
)
def test_wire_canonicalises_whitespace_padding(
    src_id: UUID,
    src_name: str,
    tgt_id: UUID,
    tgt_name: str,
    pad_left: str,
    pad_right: str,
) -> None:
    """Padded name equals the unpadded version after construction."""
    # If the body itself starts/ends with whitespace the property doesn't
    # hold (strip would consume it too); the generator alphabet excludes
    # whitespace, but assume() is the documented safety net.
    assume(src_name == src_name.strip() and tgt_name == tgt_name.strip())
    padded = Wire(
        source_asset_id=src_id,
        source_port_name=pad_left + src_name + pad_right,
        target_asset_id=tgt_id,
        target_port_name=pad_left + tgt_name + pad_right,
    )
    unpadded = Wire(
        source_asset_id=src_id,
        source_port_name=src_name,
        target_asset_id=tgt_id,
        target_port_name=tgt_name,
    )
    assert padded == unpadded
    assert hash(padded) == hash(unpadded)


@pytest.mark.unit
@given(
    src_id=st.uuids(),
    tgt_id=st.uuids(),
    overlong_body=st.text(
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
        min_size=WIRE_PORT_NAME_MAX_LENGTH + 1,
        max_size=WIRE_PORT_NAME_MAX_LENGTH + 50,
    ),
)
def test_wire_rejects_overlong_names(src_id: UUID, tgt_id: UUID, overlong_body: str) -> None:
    """Any name longer than the cap raises (asymmetric on which side fails
    first, but at least one of source/target invalidates)."""
    with pytest.raises(InvalidWireError):
        Wire(
            source_asset_id=src_id,
            source_port_name=overlong_body,
            target_asset_id=tgt_id,
            target_port_name="ok",
        )


@pytest.mark.unit
@given(
    src_id=st.uuids(),
    src_name=_PORT_NAME_BODY,
    tgt_id=st.uuids(),
    tgt_name=_PORT_NAME_BODY,
)
def test_equal_wires_collapse_in_a_frozenset(
    src_id: UUID, src_name: str, tgt_id: UUID, tgt_name: str
) -> None:
    """Two Wires with identical tuples deduplicate via hash + eq."""
    w1 = Wire(
        source_asset_id=src_id,
        source_port_name=src_name,
        target_asset_id=tgt_id,
        target_port_name=tgt_name,
    )
    w2 = Wire(
        source_asset_id=src_id,
        source_port_name=src_name,
        target_asset_id=tgt_id,
        target_port_name=tgt_name,
    )
    assert frozenset({w1, w2}) == frozenset({w1})
