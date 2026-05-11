"""Evolver: replay events to reconstruct Practice state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `PracticeEvent` without a matching match arm here.

Status mapping per event type:
  - `PracticeDefined`    -> DEFINED   (genesis; version=None)
  - `PracticeVersioned`  -> VERSIONED (version=event.version_tag;
                                        multi-source: Defined | Versioned)
  - `PracticeDeprecated` -> DEPRECATED (version preserved;
                                        multi-source: Defined | Versioned)

Mirrors Method's transition evolver shape (Recipe 6b) and
Capability's (Equipment 5f-2). `version` is mutated by
PracticeVersioned and PRESERVED by PracticeDeprecated as the audit
signal of the last revision before deprecation.

**Critical invariant**: every transition arm MUST carry
`method_id`, `site_id`, AND `version` through from prior state.
Constructing `Practice(id=..., name=..., status=...)` without
explicitly passing the carry-through fields would silently change
them. The transition arms explicitly pass each.

Transition events applied to empty state raise ValueError: they can
never appear before `PracticeDefined` in a well-formed stream. The
`_require_state` helper keeps per-arm bodies short (precedent
locked by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.recipe.aggregates.practice.events import (
    PracticeDefined,
    PracticeDeprecated,
    PracticeEvent,
    PracticeVersioned,
)
from cora.recipe.aggregates.practice.state import (
    Practice,
    PracticeName,
    PracticeStatus,
)


def _require_state(state: Practice | None, event_type: str) -> Practice:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


def evolve(state: Practice | None, event: PracticeEvent) -> Practice:
    """Apply one event to the current state."""
    match event:
        case PracticeDefined(
            practice_id=practice_id,
            name=name,
            method_id=method_id,
            site_id=site_id,
        ):
            _ = state  # PracticeDefined is the genesis event; prior state ignored
            return Practice(
                id=practice_id,
                name=PracticeName(name),
                method_id=method_id,
                site_id=site_id,
                status=PracticeStatus.DEFINED,
                # version defaults to None.
            )
        case PracticeVersioned(version_tag=version_tag):
            prior = _require_state(state, "PracticeVersioned")
            return Practice(
                id=prior.id,
                name=prior.name,
                method_id=prior.method_id,
                site_id=prior.site_id,
                status=PracticeStatus.VERSIONED,
                version=version_tag,
            )
        case PracticeDeprecated():
            prior = _require_state(state, "PracticeDeprecated")
            return Practice(
                id=prior.id,
                name=prior.name,
                method_id=prior.method_id,
                site_id=prior.site_id,
                status=PracticeStatus.DEPRECATED,
                # version preserved across deprecation.
                version=prior.version,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[PracticeEvent]) -> Practice | None:
    """Replay a stream of events from the empty initial state."""
    state: Practice | None = None
    for event in events:
        state = evolve(state, event)
    return state
