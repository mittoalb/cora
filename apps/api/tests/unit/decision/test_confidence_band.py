"""Unit tests for the ConfidenceBand enum + confidence_band() derivation."""

import pytest

from cora.decision.aggregates.decision import (
    CONFIDENCE_BAND_CERTAIN_MIN,
    CONFIDENCE_BAND_HIGH_MIN,
    CONFIDENCE_BAND_MEDIUM_MIN,
    ConfidenceBand,
    confidence_band,
)


@pytest.mark.unit
def test_confidence_band_enum_values() -> None:
    """Operator-facing strings; consumers read them as labels."""
    assert ConfidenceBand.LOW == "Low"
    assert ConfidenceBand.MEDIUM == "Medium"
    assert ConfidenceBand.HIGH == "High"
    assert ConfidenceBand.CERTAIN == "Certain"


@pytest.mark.unit
def test_confidence_band_returns_none_for_none() -> None:
    """Preserves the not-set distinction; never silently maps to Low."""
    assert confidence_band(None) is None


@pytest.mark.unit
def test_confidence_band_boundaries_match_documented_thresholds() -> None:
    """Locks the literature-default thresholds against silent drift."""
    assert CONFIDENCE_BAND_MEDIUM_MIN == 0.3
    assert CONFIDENCE_BAND_HIGH_MIN == 0.7
    assert CONFIDENCE_BAND_CERTAIN_MIN == 0.95


@pytest.mark.unit
@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.0, ConfidenceBand.LOW),
        (0.1, ConfidenceBand.LOW),
        (0.299, ConfidenceBand.LOW),
        # Boundary: 0.3 is inclusive into Medium
        (0.3, ConfidenceBand.MEDIUM),
        (0.5, ConfidenceBand.MEDIUM),
        (0.699, ConfidenceBand.MEDIUM),
        # Boundary: 0.7 is inclusive into High
        (0.7, ConfidenceBand.HIGH),
        (0.85, ConfidenceBand.HIGH),
        (0.949, ConfidenceBand.HIGH),
        # Boundary: 0.95 is inclusive into Certain (high-stakes threshold)
        (0.95, ConfidenceBand.CERTAIN),
        (0.99, ConfidenceBand.CERTAIN),
        (1.0, ConfidenceBand.CERTAIN),
    ],
)
def test_confidence_band_classification(confidence: float, expected: ConfidenceBand) -> None:
    assert confidence_band(confidence) is expected


@pytest.mark.unit
def test_confidence_band_clamps_negative_to_low() -> None:
    """Defensive: stale projection input outside [0, 1] should not
    crash; clamps to nearest segment so consumers don't fail on
    bad data. Note: validate_confidence rejects negatives at write
    time; this is purely a read-side defensive behavior."""
    assert confidence_band(-0.5) is ConfidenceBand.LOW


@pytest.mark.unit
def test_confidence_band_clamps_over_one_to_certain() -> None:
    """Same defensive behavior at the upper end."""
    assert confidence_band(1.5) is ConfidenceBand.CERTAIN


@pytest.mark.unit
def test_confidence_band_returns_none_for_nan() -> None:
    """Defensive: NaN means 'value is meaningless'. Without
    an explicit check, NaN would fall through to Certain
    (all NaN comparisons are False), the worst possible
    silent default. Returns None instead."""
    assert confidence_band(float("nan")) is None
