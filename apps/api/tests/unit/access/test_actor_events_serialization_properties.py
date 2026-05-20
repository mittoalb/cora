"""Round-trip property tests for Actor event (de)serialization.

For every Actor event, the pair `(to_payload, from_stored)` must be a
round-trip:

    from_stored(StoredEvent(payload=to_payload(e), event_type=event_type_name(e), ...)) == e

This is THE classic event-sourcing forward-compat trap: someone adds a
field to an event class, updates `to_payload` and `from_stored`, and the
example tests cover the happy path — but a generated input that hits an
edge case (extreme datetime, all-ASCII-zero UUID, max-length string)
exposes a missed field or a parser drift the example tests didn't catch.

A surviving property here would have caught the kind of bug where
`from_stored` silently substitutes a default for a new required field,
leaving old streams folding to a different state than they had before the
schema change.

Iter D.1 of the testing-techniques rollout. Pattern lifts verbatim to
every other BC's event-serialization tests; first home is Access because
it's the pilot.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.access.aggregates.actor import (
    ActorDeactivated,
    ActorKind,
    ActorRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

if TYPE_CHECKING:
    from uuid import UUID

ACTOR_NAME_MAX_LENGTH = 200
_FIXED_DT = datetime(2026, 1, 1, tzinfo=UTC)

_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=ACTOR_NAME_MAX_LENGTH,
)
_KIND = st.sampled_from(list(ActorKind))
# Events carry tz-aware (UTC) timestamps in production (Clock port returns
# UTC); restrict the strategy to match. Hypothesis' `datetimes()` defaults
# to naive datetimes, which would not round-trip through `datetime.isoformat`
# + `datetime.fromisoformat` identically in all cases.
_AWARE_DATETIME = st.datetimes(timezones=st.just(UTC))


def _wrap_as_stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    """Minimal StoredEvent envelope; only event_type + payload matter for from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Actor",
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
@given(
    actor_id=st.uuids(),
    name=_NAME,
    occurred_at=_AWARE_DATETIME,
    kind=_KIND,
)
def test_actor_registered_payload_round_trip(
    actor_id: UUID, name: str, occurred_at: datetime, kind: ActorKind
) -> None:
    """For any ActorRegistered, payload round-trips through StoredEvent."""
    assume(name == name.strip())
    original = ActorRegistered(actor_id=actor_id, name=name, occurred_at=occurred_at, kind=kind)
    stored = _wrap_as_stored(event_type_name(original), to_payload(original))
    reconstructed = from_stored(stored)
    assert reconstructed == original


@pytest.mark.unit
@given(actor_id=st.uuids(), occurred_at=_AWARE_DATETIME)
def test_actor_deactivated_payload_round_trip(actor_id: UUID, occurred_at: datetime) -> None:
    """For any ActorDeactivated, payload round-trips through StoredEvent."""
    original = ActorDeactivated(actor_id=actor_id, occurred_at=occurred_at)
    stored = _wrap_as_stored(event_type_name(original), to_payload(original))
    reconstructed = from_stored(stored)
    assert reconstructed == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Stream contaminated with foreign event_type → ValueError, not silent drop."""
    stored = _wrap_as_stored("NotAnActorEvent", {})
    with pytest.raises(ValueError, match="Unknown ActorEvent event_type"):
        from_stored(stored)
