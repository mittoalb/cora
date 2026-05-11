"""Evolver: replay events to reconstruct Capability state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CapabilityEvent` without a matching match arm here.

Status mapping per event type (5a only ships the genesis event;
5f+ will add the transitions):
  - `CapabilityDefined` -> DEFINED  (genesis)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `SubjectMounted -> MOUNTED` /
`ActorDeactivated -> is_active=False`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityEvent,
)
from cora.equipment.aggregates.capability.state import (
    Capability,
    CapabilityName,
    CapabilityStatus,
)


def evolve(state: Capability | None, event: CapabilityEvent) -> Capability:
    """Apply one event to the current state."""
    match event:
        case CapabilityDefined(capability_id=capability_id, name=name):
            _ = state  # CapabilityDefined is the genesis event; prior state ignored
            return Capability(
                id=capability_id,
                name=CapabilityName(name),
                status=CapabilityStatus.DEFINED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CapabilityEvent]) -> Capability | None:
    """Replay a stream of events from the empty initial state."""
    state: Capability | None = None
    for event in events:
        state = evolve(state, event)
    return state
