"""Unit tests for the Drawing value object + DrawingSystem enum."""

from dataclasses import FrozenInstanceError

import pytest

from cora.equipment.aggregates._drawing import (
    DRAWING_NUMBER_MAX_LENGTH,
    DRAWING_REVISION_MAX_LENGTH,
    Drawing,
    DrawingSystem,
    InvalidDrawingError,
    InvalidDrawingNumberError,
    InvalidDrawingRevisionError,
)


@pytest.mark.unit
def test_drawing_system_v1_values() -> None:
    """Pinned: v1 enum values match the document-system identifiers
    the design memo names."""
    assert DrawingSystem.ICMS.value == "ICMS"
    assert DrawingSystem.EDMS.value == "EDMS"
    assert DrawingSystem.DOI.value == "DOI"


@pytest.mark.unit
def test_drawing_constructs_with_valid_inputs() -> None:
    d = Drawing(system=DrawingSystem.ICMS, number="P4105090404-210000-00", revision="A")
    assert d.system is DrawingSystem.ICMS
    assert d.number == "P4105090404-210000-00"
    assert d.revision == "A"


@pytest.mark.unit
def test_drawing_revision_defaults_to_none() -> None:
    """Pinned: `revision = None` is the 'resolves to latest' sentinel
    (ISO 7200 / DOI / EDMS default-resolution semantics)."""
    d = Drawing(system=DrawingSystem.ICMS, number="P4105090404-210000-00")
    assert d.revision is None


@pytest.mark.unit
def test_drawing_trims_number_and_revision() -> None:
    d = Drawing(
        system=DrawingSystem.ICMS,
        number="  P4105090404-210000-00  ",
        revision="  A  ",
    )
    assert d.number == "P4105090404-210000-00"
    assert d.revision == "A"


@pytest.mark.unit
def test_drawing_rejects_empty_number() -> None:
    with pytest.raises(InvalidDrawingNumberError) as info:
        Drawing(system=DrawingSystem.ICMS, number="")
    assert info.value.value == ""


@pytest.mark.unit
def test_drawing_rejects_whitespace_only_number() -> None:
    with pytest.raises(InvalidDrawingNumberError) as info:
        Drawing(system=DrawingSystem.ICMS, number="   ")
    assert info.value.value == "   "


@pytest.mark.unit
def test_drawing_rejects_oversized_number() -> None:
    overlong = "x" * (DRAWING_NUMBER_MAX_LENGTH + 1)
    with pytest.raises(InvalidDrawingNumberError) as info:
        Drawing(system=DrawingSystem.ICMS, number=overlong)
    assert info.value.value == overlong


@pytest.mark.unit
def test_drawing_rejects_empty_revision_string() -> None:
    """Empty revision strings are a footgun (caller probably meant
    'latest'); force the caller to use None explicitly."""
    with pytest.raises(InvalidDrawingRevisionError) as info:
        Drawing(system=DrawingSystem.ICMS, number="X-001", revision="")
    assert info.value.value == ""


@pytest.mark.unit
def test_drawing_rejects_whitespace_only_revision() -> None:
    with pytest.raises(InvalidDrawingRevisionError) as info:
        Drawing(system=DrawingSystem.ICMS, number="X-001", revision="   ")
    assert info.value.value == "   "


@pytest.mark.unit
def test_drawing_rejects_oversized_revision() -> None:
    overlong = "x" * (DRAWING_REVISION_MAX_LENGTH + 1)
    with pytest.raises(InvalidDrawingRevisionError) as info:
        Drawing(system=DrawingSystem.ICMS, number="X-001", revision=overlong)
    assert info.value.value == overlong


@pytest.mark.unit
def test_drawing_accepts_max_length_number_and_revision() -> None:
    """Boundary check: exactly MAX_LENGTH is accepted; only MAX+1 is
    rejected."""
    d = Drawing(
        system=DrawingSystem.ICMS,
        number="x" * DRAWING_NUMBER_MAX_LENGTH,
        revision="r" * DRAWING_REVISION_MAX_LENGTH,
    )
    assert len(d.number) == DRAWING_NUMBER_MAX_LENGTH
    assert d.revision is not None
    assert len(d.revision) == DRAWING_REVISION_MAX_LENGTH


@pytest.mark.unit
def test_invalid_drawing_number_error_carries_value() -> None:
    """`.value` carries the original untrimmed input; route-handler
    surfaces `str(exc)` containing the formatted hint."""
    err = InvalidDrawingNumberError("  ")
    assert err.value == "  "
    assert "number" in str(err)


@pytest.mark.unit
def test_invalid_drawing_revision_error_carries_value() -> None:
    err = InvalidDrawingRevisionError("")
    assert err.value == ""
    assert "revision" in str(err)
    assert "None" in str(err)


@pytest.mark.unit
def test_invalid_drawing_number_and_revision_errors_subclass_base() -> None:
    """Routes catch the base `InvalidDrawingError`; tests catch the
    specific subclass when they need to discriminate."""
    assert issubclass(InvalidDrawingNumberError, InvalidDrawingError)
    assert issubclass(InvalidDrawingRevisionError, InvalidDrawingError)
    with pytest.raises(InvalidDrawingError):
        Drawing(system=DrawingSystem.ICMS, number="")
    with pytest.raises(InvalidDrawingError):
        Drawing(system=DrawingSystem.ICMS, number="X-001", revision="")


@pytest.mark.unit
def test_drawing_is_frozen() -> None:
    d = Drawing(system=DrawingSystem.ICMS, number="X-001")
    with pytest.raises(FrozenInstanceError):
        d.number = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_drawing_equality_is_structural() -> None:
    a = Drawing(system=DrawingSystem.ICMS, number="X-001", revision="A")
    b = Drawing(system=DrawingSystem.ICMS, number="  X-001 ", revision=" A ")
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_drawing_with_different_system_is_not_equal() -> None:
    a = Drawing(system=DrawingSystem.ICMS, number="X-001")
    b = Drawing(system=DrawingSystem.EDMS, number="X-001")
    assert a != b


@pytest.mark.unit
@pytest.mark.parametrize("explicit_revision", ["A", "1", "rev-0", "v2.3"])
def test_drawing_with_none_revision_differs_from_any_explicit_revision(
    explicit_revision: str,
) -> None:
    """`None` (latest) is NOT equal to any specific revision string,
    even short or numeric ones."""
    latest = Drawing(system=DrawingSystem.ICMS, number="X-001")
    pinned = Drawing(system=DrawingSystem.ICMS, number="X-001", revision=explicit_revision)
    assert latest != pinned


@pytest.mark.unit
def test_drawing_lives_in_a_frozenset() -> None:
    d = Drawing(system=DrawingSystem.ICMS, number="X-001")
    assert d in {d}
