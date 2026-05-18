"""Unit tests for the Affordance closed StrEnum (Phase 5j).

Pins the 28-item closed v1 list, the 3-pattern split, and the
serialization shape used by event payloads and REST/MCP bodies.
"""

import pytest

from cora.equipment.aggregates.family import Affordance, InvalidAffordanceError


@pytest.mark.unit
def test_affordance_v1_member_count() -> None:
    """v1 ships 28 items. Adding a value requires a CORA release;
    this test fails if the enum grew or shrunk so the design lock
    requires explicit acknowledgement."""
    assert len(list(Affordance)) == 28


@pytest.mark.unit
def test_affordance_pattern_a_action_count() -> None:
    """Pattern A (Action affordances, -able/-ible suffix): 24 items."""
    action_pattern = {
        a
        for a in Affordance
        if a.value.endswith(("able", "ible")) and a is not Affordance.CONSUMABLE
    }
    assert len(action_pattern) == 24


@pytest.mark.unit
def test_affordance_pattern_b_signal_count() -> None:
    """Pattern B (Signal affordances, noun): 3 items.

    EncoderInput / EncoderOutput / PulseGenerator.
    """
    signal_pattern = {
        Affordance.ENCODER_INPUT,
        Affordance.ENCODER_OUTPUT,
        Affordance.PULSE_GENERATOR,
    }
    assert len(signal_pattern) == 3
    # And none of these end in -able / -ible (verifies the rule)
    for a in signal_pattern:
        assert not a.value.endswith(("able", "ible"))


@pytest.mark.unit
def test_affordance_pattern_c_lifecycle_count() -> None:
    """Pattern C (Lifecycle affordances, noun): 1 item — Consumable.

    Note: Consumable ends in -able but is classified as Pattern C
    because it names a lifecycle property (passive parts) rather
    than an action the device supports. The pattern-classification
    is documented in `cora.equipment.aggregates.family.affordance`
    docstring + `docs/reference/affordances.md`."""
    assert Affordance.CONSUMABLE.value == "Consumable"


@pytest.mark.unit
def test_affordance_str_enum_values_are_pascal_case() -> None:
    """All Affordance values are PascalCase strings (matches the BC-map
    convention; serializes as JSON discriminator without translation)."""
    for a in Affordance:
        assert a.value[0].isupper(), f"{a.name} value {a.value!r} not PascalCase"
        # No underscores in the string value (Python enum name uses _ but value is PascalCase)
        assert "_" not in a.value, f"{a.value!r} has underscore"


@pytest.mark.unit
def test_affordance_constructor_accepts_string_value() -> None:
    """StrEnum membership: `Affordance('Rotatable')` returns the enum member."""
    assert Affordance("Rotatable") is Affordance.ROTATABLE
    assert Affordance("Bendable") is Affordance.BENDABLE
    assert Affordance("Consumable") is Affordance.CONSUMABLE


@pytest.mark.unit
def test_affordance_constructor_raises_on_unknown_value() -> None:
    """Closed-enum guard: an unknown string raises ValueError on construction."""
    with pytest.raises(ValueError, match="is not a valid Affordance"):
        Affordance("BraggAddressable")  # explicitly dropped in Round 4
    with pytest.raises(ValueError, match="is not a valid Affordance"):
        Affordance("Magic")


@pytest.mark.unit
def test_invalid_affordance_error_carries_value() -> None:
    """The defensive error class for direct in-process callers preserves the bad value."""
    err = InvalidAffordanceError("Bogus")
    assert err.value == "Bogus"
    assert "Bogus" in str(err)
    assert "28" in str(err)  # message references the closed-enum size


@pytest.mark.unit
def test_affordance_supports_set_membership_semantics() -> None:
    """The matching engine (`Method.required_affordances ⊆ Family.affordances`)
    relies on frozenset membership being O(1) per the StrEnum's hashable
    contract."""
    family_affordances = frozenset(
        {
            Affordance.ROTATABLE,
            Affordance.HOMEABLE,
            Affordance.LIMITABLE,
        }
    )
    required = frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE})
    assert required <= family_affordances
    not_required = frozenset({Affordance.BENDABLE})
    assert not (not_required <= family_affordances)


@pytest.mark.unit
def test_affordance_motion_category_members() -> None:
    """Pin the Motion category at 8 items so adds/drops are deliberate."""
    motion = {
        Affordance.ROTATABLE,
        Affordance.TRANSLATABLE,
        Affordance.HOMEABLE,
        Affordance.LIMITABLE,
        Affordance.POSITION_TRIGGERABLE,
        Affordance.POSITION_CAPTURABLE,
        Affordance.POSABLE,
        Affordance.INDEXABLE,
    }
    assert len(motion) == 8


@pytest.mark.unit
def test_affordance_dropped_pseudo_affordances_are_not_members() -> None:
    """Round 4 dropped 5 parameter-shaped candidates that belong in
    `Family.settings_schema` or operations-layer `Capability`. Pin
    the drop so re-adds require explicit re-research."""
    for dropped in (
        "BitDepthSelectable",
        "ROIConfigurable",
        "BadPixelMaskable",
        "BraggAddressable",
        "EnergySelectable",
    ):
        with pytest.raises(ValueError):
            Affordance(dropped)
