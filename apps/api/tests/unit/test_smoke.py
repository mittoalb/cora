"""Smoke test to verify the test harness and package import work."""

import pytest

import cora


@pytest.mark.unit
def test_package_importable() -> None:
    assert cora.__version__ == "0.1.0"
