"""Property-based tests for the Drawing value object.

Complements `test_drawing_value_object.py` with universal claims
over the generated input space:

  - For any valid (system, number, revision) triple, construction
    succeeds and round-trips.
  - For any valid (system, number) with revision omitted, construction
    succeeds and revision is None.
  - For any padded number, the canonical Drawing equals the unpadded
    version (covers BOTH revision-present and revision-None branches).
  - For any blank (whitespace-only) number or revision, construction
    raises the field-specific error variant.
  - For any overlong number or revision, construction raises the
    field-specific error variant.
  - Equal-by-triple Drawings share a hash (frozenset dedup).
"""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment._drawing import (
    DRAWING_NUMBER_MAX_LENGTH,
    DRAWING_REVISION_MAX_LENGTH,
    Drawing,
    DrawingSystem,
)
from cora.equipment.errors import (
    InvalidDrawingNumberError,
    InvalidDrawingRevisionError,
)

_NUMBER_BODY = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=DRAWING_NUMBER_MAX_LENGTH,
)
_REVISION_BODY = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=DRAWING_REVISION_MAX_LENGTH,
)
_SYSTEM = st.sampled_from(list(DrawingSystem))
_WS_PAD = st.text(alphabet=" \t\n\r", min_size=1, max_size=5)
_BLANK = st.text(alphabet=" \t\n\r", min_size=0, max_size=10)


@pytest.mark.unit
@given(system=_SYSTEM, number=_NUMBER_BODY)
def test_drawing_constructs_for_any_valid_pair_without_revision(
    system: DrawingSystem, number: str
) -> None:
    """Any (system, number) pair with revision omitted builds; revision
    defaults to None (the 'latest' sentinel)."""
    d = Drawing(system=system, number=number)
    assert d.system is system
    assert d.number == number
    assert d.revision is None


@pytest.mark.unit
@given(system=_SYSTEM, number=_NUMBER_BODY, revision=_REVISION_BODY)
def test_drawing_constructs_for_any_valid_triple(
    system: DrawingSystem, number: str, revision: str
) -> None:
    """Any valid (system, number, revision) triple builds and round-trips
    its fields."""
    d = Drawing(system=system, number=number, revision=revision)
    assert d.system is system
    assert d.number == number
    assert d.revision == revision


@pytest.mark.unit
@given(
    system=_SYSTEM,
    number=_NUMBER_BODY,
    revision=_REVISION_BODY,
    pad_l=_WS_PAD,
    pad_r=_WS_PAD,
)
def test_drawing_canonicalises_whitespace_padding(
    system: DrawingSystem,
    number: str,
    revision: str,
    pad_l: str,
    pad_r: str,
) -> None:
    """A padded Drawing equals the unpadded one after trim (with both
    number and revision present)."""
    assume(number == number.strip() and revision == revision.strip())
    padded = Drawing(
        system=system,
        number=pad_l + number + pad_r,
        revision=pad_l + revision + pad_r,
    )
    unpadded = Drawing(system=system, number=number, revision=revision)
    assert padded == unpadded
    assert hash(padded) == hash(unpadded)


@pytest.mark.unit
@given(
    system=_SYSTEM,
    number=_NUMBER_BODY,
    pad_l=_WS_PAD,
    pad_r=_WS_PAD,
)
def test_drawing_canonicalises_padded_number_when_revision_is_none(
    system: DrawingSystem,
    number: str,
    pad_l: str,
    pad_r: str,
) -> None:
    """Covers the 'Mount with latest-resolution' branch: padded number
    with revision omitted equals the unpadded version, and revision
    stays None through trimming."""
    assume(number == number.strip())
    padded = Drawing(system=system, number=pad_l + number + pad_r)
    unpadded = Drawing(system=system, number=number)
    assert padded == unpadded
    assert hash(padded) == hash(unpadded)
    assert padded.revision is None


@pytest.mark.unit
@given(
    system=_SYSTEM,
    overlong_number=st.text(
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
        min_size=DRAWING_NUMBER_MAX_LENGTH + 1,
        max_size=DRAWING_NUMBER_MAX_LENGTH + 50,
    ),
)
def test_drawing_rejects_overlong_number(system: DrawingSystem, overlong_number: str) -> None:
    """Any number beyond the cap raises the number-specific error
    carrying the original untrimmed value."""
    with pytest.raises(InvalidDrawingNumberError) as info:
        Drawing(system=system, number=overlong_number)
    assert info.value.value == overlong_number


@pytest.mark.unit
@given(
    system=_SYSTEM,
    number=_NUMBER_BODY,
    overlong_revision=st.text(
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
        min_size=DRAWING_REVISION_MAX_LENGTH + 1,
        max_size=DRAWING_REVISION_MAX_LENGTH + 50,
    ),
)
def test_drawing_rejects_overlong_revision(
    system: DrawingSystem, number: str, overlong_revision: str
) -> None:
    """Any revision beyond the cap raises the revision-specific error
    carrying the original untrimmed value."""
    with pytest.raises(InvalidDrawingRevisionError) as info:
        Drawing(system=system, number=number, revision=overlong_revision)
    assert info.value.value == overlong_revision


@pytest.mark.unit
@given(system=_SYSTEM, blank=_BLANK)
def test_drawing_rejects_blank_number(system: DrawingSystem, blank: str) -> None:
    """Any whitespace-only or empty number raises the number-specific
    error (covers both empty-string and whitespace-only paths)."""
    with pytest.raises(InvalidDrawingNumberError) as info:
        Drawing(system=system, number=blank)
    assert info.value.value == blank


@pytest.mark.unit
@given(system=_SYSTEM, number=_NUMBER_BODY, blank=_BLANK)
def test_drawing_rejects_blank_revision(system: DrawingSystem, number: str, blank: str) -> None:
    """Any present-but-blank revision raises the revision-specific error.
    `revision=None` is the only sanctioned 'latest' signal."""
    with pytest.raises(InvalidDrawingRevisionError) as info:
        Drawing(system=system, number=number, revision=blank)
    assert info.value.value == blank


@pytest.mark.unit
@given(system=_SYSTEM, number=_NUMBER_BODY, revision=_REVISION_BODY)
def test_equal_drawings_collapse_in_a_frozenset(
    system: DrawingSystem, number: str, revision: str
) -> None:
    d1 = Drawing(system=system, number=number, revision=revision)
    d2 = Drawing(system=system, number=number, revision=revision)
    assert frozenset({d1, d2}) == frozenset({d1})
