"""Round-trip property tests for Zone event (de)serialization.

Mirror of `tests/unit/access/test_actor_events_serialization_properties.py`
on the Trust BC's single Zone event type. Property:

    from_stored(StoredEvent(payload=to_payload(e), event_type=...)) == e

Catches the classic ES forward-compat trap (add a field, update `to_payload`
+ `from_stored`, miss an edge case the example tests don't reach).

Pattern lifts verbatim from the Access sibling file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.zone import (
    ZONE_NAME_MAX_LENGTH,
    ZoneDefined,
    event_type_name,
    from_stored,
    to_payload,
)
from tests._strategies import aware_datetimes, make_stored_event, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(max_size=ZONE_NAME_MAX_LENGTH)
_AWARE_DATETIME = aware_datetimes()


@pytest.mark.unit
@given(zone_id=st.uuids(), name=_NAME, occurred_at=_AWARE_DATETIME)
def test_zone_defined_payload_round_trip(zone_id: UUID, name: str, occurred_at: datetime) -> None:
    """For any ZoneDefined, payload round-trips through StoredEvent."""
    assume(name == name.strip())
    original = ZoneDefined(zone_id=zone_id, name=name, occurred_at=occurred_at)
    stored = make_stored_event(
        stream_type="Zone",
        event_type=event_type_name(original),
        payload=to_payload(original),
    )
    reconstructed = from_stored(stored)
    assert reconstructed == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Stream contaminated with foreign event_type → ValueError, not silent drop."""
    stored = make_stored_event(stream_type="Zone", event_type="NotAZoneEvent", payload={})
    with pytest.raises(ValueError, match="Unknown ZoneEvent event_type"):
        from_stored(stored)
