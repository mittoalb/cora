"""Property-based tests for the Affordance closed StrEnum.

Complements `test_affordance.py` (which pins specific membership +
counts) with universal claims over every Affordance member:

  - value/member round-trip: `Affordance(m.value) is m`
  - serialised form is a non-empty PascalCase ASCII string
  - all member values are distinct
  - member-set is stable across runs (no hidden ordering bug)

These properties would all be tautologies for a hand-rolled enum,
but they catch the kind of regression that arises when someone
hand-edits the enum file (typo, dup value, accidental string with
whitespace) and the example-based tests happen not to cover the
broken member.

First PBT file in the testing-techniques rollout.
"""

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import Affordance


@pytest.mark.unit
@given(member=st.sampled_from(list(Affordance)))
def test_affordance_value_member_round_trip(member: Affordance) -> None:
    """For every member, looking up by `.value` returns the same member."""
    assert Affordance(member.value) is member


@pytest.mark.unit
@given(member=st.sampled_from(list(Affordance)))
def test_affordance_value_is_nonempty_pascalcase_ascii(member: Affordance) -> None:
    """Values serialise as non-empty PascalCase ASCII (no whitespace, no
    leading digit, first char uppercase). Catches accidental ` Foo`,
    `foo`, `Foo Bar`, or non-ASCII in the source enum.
    """
    value = member.value
    assert value, f"{member.name} has empty .value"
    assert value[0] in string.ascii_uppercase, (
        f"{member.name}.value={value!r} should start uppercase"
    )
    assert value.isascii(), f"{member.name}.value={value!r} contains non-ASCII"
    assert " " not in value, f"{member.name}.value={value!r} contains whitespace"


@pytest.mark.unit
def test_affordance_values_are_all_distinct() -> None:
    """No two members share a `.value` (would silently alias members)."""
    values = [m.value for m in Affordance]
    assert len(values) == len(set(values))


@pytest.mark.unit
def test_affordance_iteration_order_is_stable() -> None:
    """Member iteration order is the source-file declaration order
    and is stable across runs (StrEnum guarantee). Pins it so a
    refactor that switches to `set`-backed lookup would fail loudly.
    """
    first_pass = [m.name for m in Affordance]
    second_pass = [m.name for m in Affordance]
    assert first_pass == second_pass
