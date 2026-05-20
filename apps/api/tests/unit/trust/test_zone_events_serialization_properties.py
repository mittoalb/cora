"""Round-trip property tests for Zone event (de)serialization.

Mirror of `tests/unit/access/test_actor_events_serialization_properties.py`
on the Trust BC's single Zone event type. Property:

    from_stored(StoredEvent(payload=to_payload(e), event_type=...)) == e

Catches the classic ES forward-compat trap (add a field, update `to_payload`
+ `from_stored`, miss an edge case the example tests don't reach).

Iter D.2 of the testing-techniques rollout. Pattern lifts verbatim from
the Access sibling file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.zone import (
    ZONE_NAME_MAX_LENGTH,
    ZoneDefined,
    event_type_name,
    from_stored,
    to_payload,
)

if TYPE_CHECKING:
    from uuid import UUID

_FIXED_DT = datetime(2026, 1, 1, tzinfo=UTC)

_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=ZONE_NAME_MAX_LENGTH,
)
_AWARE_DATETIME = st.datetimes(timezones=st.just(UTC))


def _wrap_as_stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Zone",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_FIXED_DT,
        recorded_at=_FIXED_DT,
    )


@pytest.mark.unit
@given(zone_id=st.uuids(), name=_NAME, occurred_at=_AWARE_DATETIME)
def test_zone_defined_payload_round_trip(zone_id: UUID, name: str, occurred_at: datetime) -> None:
    """For any ZoneDefined, payload round-trips through StoredEvent."""
    assume(name == name.strip())
    original = ZoneDefined(zone_id=zone_id, name=name, occurred_at=occurred_at)
    stored = _wrap_as_stored(event_type_name(original), to_payload(original))
    reconstructed = from_stored(stored)
    assert reconstructed == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Stream contaminated with foreign event_type → ValueError, not silent drop."""
    stored = _wrap_as_stored("NotAZoneEvent", {})
    with pytest.raises(ValueError, match="Unknown ZoneEvent event_type"):
        from_stored(stored)
