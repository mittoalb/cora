"""Property-based tests for the Zone evolver + replay determinism.

Mirror of `tests/unit/access/test_actor_evolver_properties.py` for the
Trust BC's Zone aggregate. Zone is simpler (one event type, genesis-only
FSM), so the property surface shrinks accordingly:

  - evolve(None, ZoneDefined) → Zone with id + name from the event.
  - fold([defined]) replays deterministically across invocations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.zone import (
    ZONE_NAME_MAX_LENGTH,
    Zone,
    ZoneDefined,
    ZoneName,
)
from cora.trust.aggregates.zone.evolver import evolve, fold

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=ZONE_NAME_MAX_LENGTH,
)
_DATETIME = st.datetimes()


@pytest.mark.unit
@given(zone_id=st.uuids(), name=_NAME, occurred_at=_DATETIME)
def test_evolve_defined_from_none_yields_zone_with_event_fields(
    zone_id: UUID, name: str, occurred_at: datetime
) -> None:
    """First-event fold: state is exactly the event's id + name."""
    assume(name == name.strip())
    state = evolve(None, ZoneDefined(zone_id=zone_id, name=name, occurred_at=occurred_at))
    assert state == Zone(id=zone_id, name=ZoneName(name))


@pytest.mark.unit
@given(zone_id=st.uuids(), name=_NAME, occurred_at=_DATETIME)
def test_fold_is_deterministic_across_replays(
    zone_id: UUID, name: str, occurred_at: datetime
) -> None:
    """Same event list folds to the same state every time — THE event-sourcing
    property. Projection replicas silently diverge if this ever breaks.
    """
    assume(name == name.strip())
    events = [ZoneDefined(zone_id=zone_id, name=name, occurred_at=occurred_at)]
    first = fold(events)
    second = fold(events)
    assert first == second
    assert first is not None
