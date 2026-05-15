"""HazardClassification discriminated-union VO kernel: NFPA704 / RiskBand / GHS / SchemeCode."""

import pytest

from cora.safety.hazard_classification import (
    GHS_VALID_PICTOGRAMS,
    NFPA704_MAX_RATING,
    NFPA704_MIN_RATING,
    NFPA704_VALID_SPECIAL,
    GHSPictogram,
    InvalidGHSPictogramCodeError,
    InvalidGHSStatementCodeError,
    InvalidNFPA704RatingError,
    InvalidNFPA704SpecialError,
    InvalidSchemeCodeError,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)

# ---------- NFPA704Rating ----------


@pytest.mark.unit
def test_nfpa704_accepts_valid_quadrants() -> None:
    rating = NFPA704Rating(health=2, flammability=1, instability=0, special=None)
    assert rating.health == 2
    assert rating.special is None


@pytest.mark.unit
def test_nfpa704_accepts_valid_special_code() -> None:
    rating = NFPA704Rating(health=0, flammability=4, instability=2, special="OX")
    assert rating.special == "OX"


@pytest.mark.unit
@pytest.mark.parametrize("axis", ["health", "flammability", "instability"])
def test_nfpa704_rejects_negative_quadrant(axis: str) -> None:
    kwargs: dict[str, object] = {"health": 0, "flammability": 0, "instability": 0}
    kwargs[axis] = -1
    with pytest.raises(InvalidNFPA704RatingError):
        NFPA704Rating(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.parametrize("axis", ["health", "flammability", "instability"])
def test_nfpa704_rejects_quadrant_above_4(axis: str) -> None:
    kwargs: dict[str, object] = {"health": 0, "flammability": 0, "instability": 0}
    kwargs[axis] = 5
    with pytest.raises(InvalidNFPA704RatingError):
        NFPA704Rating(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
def test_nfpa704_rejects_unknown_special_code() -> None:
    with pytest.raises(InvalidNFPA704SpecialError):
        NFPA704Rating(health=0, flammability=0, instability=0, special="XYZ")


@pytest.mark.unit
@pytest.mark.parametrize("axis", ["health", "flammability", "instability"])
def test_nfpa704_rejects_bool_value_via_isinstance_short_circuit(axis: str) -> None:
    """`bool` is a subclass of `int` in Python, so `isinstance(True, int)` is True.
    The constructor explicitly checks `isinstance(value, bool)` BEFORE
    `isinstance(value, int)` to refuse boolean coercion. Lock the order so a future
    'simplification' doesn't delete the bool guard and silently coerce True->1."""
    kwargs: dict[str, object] = {"health": 0, "flammability": 0, "instability": 0}
    kwargs[axis] = True
    with pytest.raises(InvalidNFPA704RatingError):
        NFPA704Rating(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
def test_nfpa704_rating_is_frozen() -> None:
    rating = NFPA704Rating(health=2, flammability=1, instability=0)
    with pytest.raises((AttributeError, TypeError)):
        rating.health = 3  # type: ignore[misc]


@pytest.mark.unit
def test_nfpa704_constants_pinned() -> None:
    assert NFPA704_MIN_RATING == 0
    assert NFPA704_MAX_RATING == 4
    assert "OX" in NFPA704_VALID_SPECIAL
    assert "W" in NFPA704_VALID_SPECIAL


# ---------- RiskBand ----------


@pytest.mark.unit
def test_risk_band_has_three_locked_values() -> None:
    assert {b.value for b in RiskBand} == {"Green", "Yellow", "Red"}


# ---------- GHSPictogram ----------


@pytest.mark.unit
def test_ghs_pictogram_accepts_valid_code() -> None:
    p = GHSPictogram(code="GHS06", statement_codes=frozenset({"H300", "H311"}))
    assert p.code == "GHS06"
    assert p.statement_codes == frozenset({"H300", "H311"})


@pytest.mark.unit
def test_ghs_pictogram_accepts_empty_statement_codes() -> None:
    p = GHSPictogram(code="GHS01")
    assert p.statement_codes == frozenset()


@pytest.mark.unit
def test_ghs_pictogram_rejects_unknown_code() -> None:
    with pytest.raises(InvalidGHSPictogramCodeError):
        GHSPictogram(code="GHS99")


@pytest.mark.unit
def test_ghs_pictogram_rejects_empty_statement_code() -> None:
    with pytest.raises(InvalidGHSStatementCodeError):
        GHSPictogram(code="GHS06", statement_codes=frozenset({"   "}))


@pytest.mark.unit
def test_ghs_pictogram_rejects_oversized_statement_code() -> None:
    with pytest.raises(InvalidGHSStatementCodeError):
        GHSPictogram(code="GHS06", statement_codes=frozenset({"H" + "1" * 50}))


@pytest.mark.unit
def test_ghs_valid_pictograms_pinned() -> None:
    assert (
        frozenset({"GHS01", "GHS02", "GHS03", "GHS04", "GHS05", "GHS06", "GHS07", "GHS08", "GHS09"})
        == GHS_VALID_PICTOGRAMS
    )


# ---------- SchemeCode ----------


@pytest.mark.unit
def test_scheme_code_accepts_valid_triple() -> None:
    s = SchemeCode(scheme="ANSI_Z136", code="Class_4", severity_label="extreme")
    assert s.scheme == "ANSI_Z136"
    assert s.code == "Class_4"
    assert s.severity_label == "extreme"


@pytest.mark.unit
def test_scheme_code_trims_fields() -> None:
    s = SchemeCode(scheme="  BSL  ", code="  BSL_2  ", severity_label="  moderate  ")
    assert s.scheme == "BSL"
    assert s.code == "BSL_2"
    assert s.severity_label == "moderate"


@pytest.mark.unit
def test_scheme_code_accepts_empty_severity_label() -> None:
    s = SchemeCode(scheme="IAEA", code="Cat_2")
    assert s.severity_label == ""


@pytest.mark.unit
def test_scheme_code_rejects_empty_scheme() -> None:
    with pytest.raises(InvalidSchemeCodeError):
        SchemeCode(scheme="   ", code="x")


@pytest.mark.unit
def test_scheme_code_rejects_empty_code() -> None:
    with pytest.raises(InvalidSchemeCodeError):
        SchemeCode(scheme="x", code="   ")


@pytest.mark.unit
def test_scheme_code_rejects_oversized_severity_label() -> None:
    with pytest.raises(InvalidSchemeCodeError):
        SchemeCode(scheme="x", code="y", severity_label="z" * 200)
