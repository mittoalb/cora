"""Property-based tests for `define_zone.decide` (Trust BC).

Mirrors the Access BC decider-PBT pattern on a Trust BC
create-style command. Universal claims across generated inputs:

  - state=None + valid command → single ZoneDefined with injected
    new_id + now + trimmed name.
  - state=Zone → ZoneAlreadyExistsError, regardless of command.
  - Pure: same (state, command, now, new_id) → same events.

First PBT extrapolation from Access (pilot) to Trust BC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.zone import (
    ZONE_NAME_MAX_LENGTH,
    Zone,
    ZoneAlreadyExistsError,
    ZoneDefined,
    ZoneName,
)
from cora.trust.features import define_zone
from cora.trust.features.define_zone import DefineZone

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=ZONE_NAME_MAX_LENGTH,
)
_DATETIME = st.datetimes()


def _zone(zone_id: UUID, name: str = "x") -> Zone:
    return Zone(id=zone_id, name=ZoneName(name))


@pytest.mark.unit
@given(name=_NAME, now=_DATETIME, new_id=st.uuids())
def test_define_zone_emits_exactly_one_event_with_injected_fields(
    name: str, now: datetime, new_id: UUID
) -> None:
    """Empty stream + valid command → single ZoneDefined with the injected ids/time."""
    assume(name == name.strip())
    events = define_zone.decide(
        state=None,
        command=DefineZone(name=name),
        now=now,
        new_id=new_id,
    )
    assert events == [ZoneDefined(zone_id=new_id, name=name, occurred_at=now)]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    now=_DATETIME,
    new_id=st.uuids(),
)
def test_define_zone_on_existing_state_always_raises_already_exists(
    existing_id: UUID, name: str, now: datetime, new_id: UUID
) -> None:
    """Any non-None state → ZoneAlreadyExistsError, regardless of command."""
    with pytest.raises(ZoneAlreadyExistsError) as exc:
        define_zone.decide(
            state=_zone(existing_id),
            command=DefineZone(name=name),
            now=now,
            new_id=new_id,
        )
    assert exc.value.zone_id == existing_id


@pytest.mark.unit
@given(name=_NAME, now=_DATETIME, new_id=st.uuids())
def test_define_zone_is_pure_same_input_same_output(name: str, now: datetime, new_id: UUID) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    assume(name == name.strip())
    command = DefineZone(name=name)
    first = define_zone.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_zone.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
