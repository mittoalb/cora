"""Unit tests for Fixture state + SlotAssetBinding VO."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureAlreadyExistsError,
    SlotAssetBinding,
)


@pytest.mark.unit
def test_slot_asset_binding_identity_is_pair() -> None:
    """Two SlotAssetBindings with identical (slot_name, asset_id) collapse in a frozenset."""
    asset_id = uuid4()
    a = SlotAssetBinding(slot_name="camera", asset_id=asset_id)
    b = SlotAssetBinding(slot_name="camera", asset_id=asset_id)
    assert {a, b} == {a}


@pytest.mark.unit
def test_slot_asset_binding_same_slot_different_assets_are_distinct() -> None:
    a = SlotAssetBinding(slot_name="cabling", asset_id=uuid4())
    b = SlotAssetBinding(slot_name="cabling", asset_id=uuid4())
    assert {a, b} == {a, b}
    assert len({a, b}) == 2


@pytest.mark.unit
def test_fixture_state_constructs_with_defaults() -> None:
    state = Fixture(
        id=uuid4(),
        assembly_id=uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=uuid4(),
    )
    assert state.slot_asset_bindings == frozenset()
    assert state.parameter_overrides == {}
    assert state.registered_at is None


@pytest.mark.unit
def test_fixture_already_exists_error_carries_id() -> None:
    target = uuid4()
    err = FixtureAlreadyExistsError(target)
    assert err.fixture_id == target
    assert str(target) in str(err)
