"""Evolver: replay events to reconstruct Capability state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CapabilityEvent` without a matching match arm here.

Status mapping per event type:
  - `CapabilityDefined`    -> DEFINED   (genesis; version=None)
  - `CapabilityVersioned`  -> VERSIONED (version=event.version_tag;
                                          multi-source: Defined | Versioned)
  - `CapabilityDeprecated` -> DEPRECATED (version preserved;
                                          multi-source: Defined | Versioned)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `SubjectMounted -> MOUNTED` /
`ActorDeactivated -> is_active=False`.

`version` is mutated by CapabilityVersioned (set to the new tag) and
PRESERVED by CapabilityDeprecated. Future events (un-deprecate slice,
if it ever ships) would have the same preserve-the-history contract.
Pre-5f-2 CapabilityDefined-only streams fold cleanly with version=None
(the additive-state pattern).

Transition events applied to empty state raise ValueError: they can
never appear before `CapabilityDefined` in a well-formed stream.
The `require_state` helper keeps per-arm bodies short (precedent
locked by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityEvent,
    CapabilitySettingsSchemaUpdated,
    CapabilityVersioned,
)
from cora.equipment.aggregates.capability.state import (
    Capability,
    CapabilityName,
    CapabilityStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Capability | None, event: CapabilityEvent) -> Capability:
    """Apply one event to the current state."""
    match event:
        case CapabilityDefined(capability_id=capability_id, name=name):
            _ = state  # CapabilityDefined is the genesis event; prior state ignored
            return Capability(
                id=capability_id,
                name=CapabilityName(name),
                status=CapabilityStatus.DEFINED,
                # version defaults to None.
            )
        case CapabilityVersioned(version_tag=version_tag):
            prior = require_state(state, "CapabilityVersioned")
            return Capability(
                id=prior.id,
                name=prior.name,
                status=CapabilityStatus.VERSIONED,
                version=version_tag,
                # settings_schema preserved across content versioning;
                # schema iteration is independent of content versioning
                # (separate CapabilitySettingsSchemaUpdated event).
                settings_schema=prior.settings_schema,
            )
        case CapabilityDeprecated():
            prior = require_state(state, "CapabilityDeprecated")
            return Capability(
                id=prior.id,
                name=prior.name,
                status=CapabilityStatus.DEPRECATED,
                # version preserved across deprecation.
                version=prior.version,
                # settings_schema preserved across deprecation; the
                # historical declaration remains visible for audit.
                settings_schema=prior.settings_schema,
            )
        case CapabilitySettingsSchemaUpdated(settings_schema=settings_schema):
            prior = require_state(state, "CapabilitySettingsSchemaUpdated")
            return Capability(
                id=prior.id,
                name=prior.name,
                status=prior.status,
                version=prior.version,
                settings_schema=settings_schema,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CapabilityEvent]) -> Capability | None:
    """Replay a stream of events from the empty initial state."""
    state: Capability | None = None
    for event in events:
        state = evolve(state, event)
    return state
