"""Evolver: replay events to reconstruct Capability state.

Status mapping per event type:
  - `CapabilityDefined`    -> DEFINED   (genesis; version=None)
  - `CapabilityVersioned`  -> VERSIONED (version=event.version_tag;
                                         declarative contract REPLACES
                                         wholesale per DLM-B)
  - `CapabilityDeprecated` -> DEPRECATED (declarative contract PRESERVED
                                          for audit; replaced_by_capability_id
                                          captured if supplied)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `FamilyVersioned`.

## Replace vs preserve on each arm

- CapabilityVersioned REPLACES required_affordances, executor_shapes,
  description, parameter_schema with the new event's values (a new
  version IS a new declaration).
- CapabilityDeprecated PRESERVES all declarative fields and ADDS the
  replaced_by_capability_id pointer. Operators reading a deprecated
  Capability still see what it declared (audit-critical).

Transition events applied to empty state raise ValueError via
`require_state` — they can never appear before `CapabilityDefined`
in a well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityEvent,
    CapabilityVersioned,
)
from cora.recipe.aggregates.capability.state import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityStatus,
)


def evolve(state: Capability | None, event: CapabilityEvent) -> Capability:
    """Apply one event to the current state."""
    match event:
        case CapabilityDefined(
            capability_id=capability_id,
            code=code,
            name=name,
            description=description,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            parameter_schema=parameter_schema,
        ):
            _ = state  # genesis event; prior state ignored
            return Capability(
                id=capability_id,
                code=CapabilityCode(code),
                name=CapabilityName(name),
                status=CapabilityStatus.DEFINED,
                description=description,
                required_affordances=required_affordances,
                executor_shapes=executor_shapes,
                parameter_schema=parameter_schema,
            )
        case CapabilityVersioned(
            version_tag=version_tag,
            description=description,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            parameter_schema=parameter_schema,
        ):
            prior = require_state(state, "CapabilityVersioned")
            return Capability(
                id=prior.id,
                code=prior.code,
                name=prior.name,
                status=CapabilityStatus.VERSIONED,
                version=version_tag,
                # Declarative contract REPLACES wholesale (a new version
                # IS a new declaration per DLM-B Pattern P).
                description=description,
                required_affordances=required_affordances,
                executor_shapes=executor_shapes,
                parameter_schema=parameter_schema,
                replaced_by_capability_id=prior.replaced_by_capability_id,
            )
        case CapabilityDeprecated(replaced_by_capability_id=replaced_by_capability_id):
            prior = require_state(state, "CapabilityDeprecated")
            return Capability(
                id=prior.id,
                code=prior.code,
                name=prior.name,
                status=CapabilityStatus.DEPRECATED,
                version=prior.version,
                # Declarative contract PRESERVED across deprecation; the
                # historical declaration stays visible for audit.
                description=prior.description,
                required_affordances=prior.required_affordances,
                executor_shapes=prior.executor_shapes,
                parameter_schema=prior.parameter_schema,
                # Set the replaced_by pointer (None if not supplied).
                replaced_by_capability_id=replaced_by_capability_id,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CapabilityEvent]) -> Capability | None:
    """Replay a stream of events from the empty initial state."""
    state: Capability | None = None
    for event in events:
        state = evolve(state, event)
    return state
