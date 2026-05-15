"""Evolver: replay events to reconstruct Supply state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `SupplyEvent` without a matching match arm here.

Status mapping per event type (10a-a):
  - `SupplyRegistered`        -> UNKNOWN   (genesis; universal initial-state convention)
  - `SupplyMarkedAvailable`   -> AVAILABLE (single-source: Unknown only)

Phase 10a-b will add four arms:
  - `SupplyDegraded`          -> DEGRADED    (sources: Unknown, Available, Recovering)
  - `SupplyMarkedUnavailable` -> UNAVAILABLE (sources: Unknown, Available, Degraded, Recovering)
  - `SupplyMarkedRecovering`  -> RECOVERING  (single-source: Unavailable)
  - `SupplyRestored`          -> AVAILABLE   (single-source: Recovering; recovery ack)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator. Same precedent as `CapabilityDefined ->
DEFINED` / `SubjectMounted -> MOUNTED`.

Transition events applied to empty state raise ValueError: they can
never appear before `SupplyRegistered` in a well-formed stream.
The shared `require_state` helper at `cora.infrastructure.evolver`
keeps per-arm bodies short (hoisted post-7e once the 11th identical
copy landed; Supply is the 11th evolver to use it on day one).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.supply.aggregates.supply.events import (
    SupplyEvent,
    SupplyMarkedAvailable,
    SupplyRegistered,
)
from cora.supply.aggregates.supply.state import (
    Supply,
    SupplyName,
    SupplyScope,
    SupplyStatus,
)


def evolve(state: Supply | None, event: SupplyEvent) -> Supply:
    """Apply one event to the current state."""
    match event:
        case SupplyRegistered(
            supply_id=supply_id,
            scope=scope,
            kind=kind,
            name=name,
        ):
            _ = state  # SupplyRegistered is the genesis event; prior state ignored
            return Supply(
                id=supply_id,
                scope=SupplyScope(scope),
                kind=kind,
                name=SupplyName(name),
                status=SupplyStatus.UNKNOWN,
            )
        case SupplyMarkedAvailable():
            prior = require_state(state, "SupplyMarkedAvailable")
            return Supply(
                id=prior.id,
                scope=prior.scope,
                kind=prior.kind,
                name=prior.name,
                status=SupplyStatus.AVAILABLE,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[SupplyEvent]) -> Supply | None:
    """Replay a stream of events from the empty initial state."""
    state: Supply | None = None
    for event in events:
        state = evolve(state, event)
    return state
