"""Evolver: replay events to reconstruct Method state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `MethodEvent` without a matching match arm here.

Status mapping per event type:
  - `MethodDefined`              -> DEFINED   (genesis; version=None,
                                                parameters_schema=None)
  - `MethodVersioned`            -> VERSIONED (version=event.version_tag;
                                                multi-source: Defined |
                                                Versioned; parameters_schema
                                                preserved)
  - `MethodDeprecated`           -> DEPRECATED (version preserved;
                                                multi-source: Defined |
                                                Versioned; parameters_schema
                                                preserved)
  - `MethodParametersSchemaUpdated` -> status preserved (orthogonal to
                                                lifecycle; updates the
                                                parameters_schema field
                                                only; 6g-a)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `CapabilityDefined → DEFINED` / `SubjectMounted →
MOUNTED`. Mirrors Capability's transition evolver shape from
Equipment 5f-2.

`needs_capabilities` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state) here. Order doesn't matter at the state
layer (set semantics for Plan-binding superset checks); the payload
already sorted in `to_payload` for persistence determinism.

`version` is mutated by MethodVersioned (set to the new tag) and
PRESERVED by MethodDeprecated. Pre-6b MethodDefined-only streams fold
cleanly with version=None (the additive-state pattern).

**Critical invariant**: every transition arm MUST carry
`needs_capabilities`, `version`, AND `parameters_schema` through from
prior state. Constructing `Method(id=..., name=..., status=...)`
without explicitly passing the additive frozenset/optional fields
would silently WIPE them to defaults. Pinned by
`test_evolve_<transition>_preserves_needs_capabilities`, the existing
`version` preservation tests, and 6g-a's
`test_evolve_<transition>_preserves_parameters_schema` cases.

Transition events applied to empty state raise ValueError: they can
never appear before `MethodDefined` in a well-formed stream. The
`require_state` helper keeps per-arm bodies short (precedent locked
by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodEvent,
    MethodParametersSchemaUpdated,
    MethodVersioned,
)
from cora.recipe.aggregates.method.state import (
    Method,
    MethodName,
    MethodStatus,
)


def evolve(state: Method | None, event: MethodEvent) -> Method:
    """Apply one event to the current state."""
    match event:
        case MethodDefined(
            method_id=method_id,
            name=name,
            needs_capabilities=needs_capabilities,
        ):
            _ = state  # MethodDefined is the genesis event; prior state ignored
            return Method(
                id=method_id,
                name=MethodName(name),
                needs_capabilities=frozenset(needs_capabilities),
                status=MethodStatus.DEFINED,
                # version defaults to None.
            )
        case MethodVersioned(version_tag=version_tag):
            prior = require_state(state, "MethodVersioned")
            return Method(
                id=prior.id,
                name=prior.name,
                needs_capabilities=prior.needs_capabilities,
                status=MethodStatus.VERSIONED,
                version=version_tag,
                parameters_schema=prior.parameters_schema,
            )
        case MethodDeprecated():
            prior = require_state(state, "MethodDeprecated")
            return Method(
                id=prior.id,
                name=prior.name,
                needs_capabilities=prior.needs_capabilities,
                status=MethodStatus.DEPRECATED,
                # version preserved across deprecation.
                version=prior.version,
                parameters_schema=prior.parameters_schema,
            )
        case MethodParametersSchemaUpdated(parameters_schema=parameters_schema):
            prior = require_state(state, "MethodParametersSchemaUpdated")
            return Method(
                id=prior.id,
                name=prior.name,
                needs_capabilities=prior.needs_capabilities,
                status=prior.status,
                version=prior.version,
                parameters_schema=parameters_schema,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[MethodEvent]) -> Method | None:
    """Replay a stream of events from the empty initial state."""
    state: Method | None = None
    for event in events:
        state = evolve(state, event)
    return state
