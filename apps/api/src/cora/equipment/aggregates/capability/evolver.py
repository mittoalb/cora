"""Evolver: replay events to reconstruct Capability state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CapabilityEvent` without a matching match arm here.

Status mapping per event type:
  - `CapabilityDefined`    -> DEFINED   (genesis; current_version=None)
  - `CapabilityVersioned`  -> VERSIONED (current_version=event.version_tag;
                                          multi-source: Defined | Versioned)
  - `CapabilityDeprecated` -> DEPRECATED (current_version preserved;
                                          multi-source: Defined | Versioned)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `SubjectMounted -> MOUNTED` /
`ActorDeactivated -> is_active=False`.

`current_version` is mutated by CapabilityVersioned (set to the new
tag) and PRESERVED by CapabilityDeprecated. Future events (un-deprecate
slice, if it ever ships) would have the same preserve-the-history
contract. Pre-5f-2 CapabilityDefined-only streams fold cleanly with
current_version=None (the additive-state pattern).

Transition events applied to empty state raise ValueError: they can
never appear before `CapabilityDefined` in a well-formed stream.
The `_require_state` helper keeps per-arm bodies short (precedent
locked by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityEvent,
    CapabilityVersioned,
)
from cora.equipment.aggregates.capability.state import (
    Capability,
    CapabilityName,
    CapabilityStatus,
)


def _require_state(state: Capability | None, event_type: str) -> Capability:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


def evolve(state: Capability | None, event: CapabilityEvent) -> Capability:
    """Apply one event to the current state."""
    match event:
        case CapabilityDefined(capability_id=capability_id, name=name):
            _ = state  # CapabilityDefined is the genesis event; prior state ignored
            return Capability(
                id=capability_id,
                name=CapabilityName(name),
                status=CapabilityStatus.DEFINED,
                # current_version defaults to None.
            )
        case CapabilityVersioned(version_tag=version_tag):
            prior = _require_state(state, "CapabilityVersioned")
            return Capability(
                id=prior.id,
                name=prior.name,
                status=CapabilityStatus.VERSIONED,
                current_version=version_tag,
            )
        case CapabilityDeprecated():
            prior = _require_state(state, "CapabilityDeprecated")
            return Capability(
                id=prior.id,
                name=prior.name,
                status=CapabilityStatus.DEPRECATED,
                # current_version preserved across deprecation.
                current_version=prior.current_version,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CapabilityEvent]) -> Capability | None:
    """Replay a stream of events from the empty initial state."""
    state: Capability | None = None
    for event in events:
        state = evolve(state, event)
    return state
