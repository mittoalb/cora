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

from typing import TYPE_CHECKING

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
from tests._strategies import aware_datetimes, make_stored_event, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

ACTOR_NAME_MAX_LENGTH = 200

_NAME = printable_ascii_text(max_size=ACTOR_NAME_MAX_LENGTH)
_KIND = st.sampled_from(list(ActorKind))
_AWARE_DATETIME = aware_datetimes()


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
    stored = make_stored_event(
        stream_type="Actor",
        event_type=event_type_name(original),
        payload=to_payload(original),
    )
    reconstructed = from_stored(stored)
    assert reconstructed == original


@pytest.mark.unit
@given(actor_id=st.uuids(), occurred_at=_AWARE_DATETIME)
def test_actor_deactivated_payload_round_trip(actor_id: UUID, occurred_at: datetime) -> None:
    """For any ActorDeactivated, payload round-trips through StoredEvent."""
    original = ActorDeactivated(actor_id=actor_id, occurred_at=occurred_at)
    stored = make_stored_event(
        stream_type="Actor",
        event_type=event_type_name(original),
        payload=to_payload(original),
    )
    reconstructed = from_stored(stored)
    assert reconstructed == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Stream contaminated with foreign event_type → ValueError, not silent drop."""
    stored = make_stored_event(stream_type="Actor", event_type="NotAnActorEvent", payload={})
    with pytest.raises(ValueError, match="Unknown ActorEvent event_type"):
        from_stored(stored)
