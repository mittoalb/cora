"""Evolver: replay events to reconstruct Method state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `MethodEvent` without a matching match arm here.

Status mapping per event type (6a only ships the genesis event;
6b will add the transitions):
  - `MethodDefined` -> DEFINED  (genesis)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `CapabilityDefined → DEFINED` /
`SubjectMounted → MOUNTED`.

`needs_capabilities` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state) here. Order doesn't matter at the state
layer (set semantics for Plan-binding superset checks); the payload
already sorted in `to_payload` for persistence determinism.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodEvent,
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
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[MethodEvent]) -> Method | None:
    """Replay a stream of events from the empty initial state."""
    state: Method | None = None
    for event in events:
        state = evolve(state, event)
    return state
