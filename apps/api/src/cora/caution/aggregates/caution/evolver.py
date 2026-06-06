"""Evolver: replay events to reconstruct Caution state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CautionEvent` without a matching match arm here.

Status mapping per event type:

  - `CautionRegistered`  -> ACTIVE     (genesis; for both top-level and supersession-child)
  - `CautionSuperseded`  -> SUPERSEDED (single-source: Active only;
                            sets `superseded_by_caution_id`; written
                            to PARENT stream during cross-aggregate
                            supersession)
  - `CautionRetired`     -> RETIRED    (single-source: Active only;
                            sets `retired_reason` from the closed
                            CautionRetireReason enum)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver` (hoisted
at the 11th identical-copy site).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.caution.aggregates.caution.events import (
    CautionEvent,
    CautionRegistered,
    CautionRetired,
    CautionSuperseded,
)
from cora.caution.aggregates.caution.state import (
    Caution,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    CautionTag,
    CautionText,
    CautionWorkaround,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Caution | None, event: CautionEvent) -> Caution:
    """Apply one event to the current state."""
    match event:
        case CautionRegistered(
            caution_id=caution_id,
            target=target,
            category=category,
            severity=severity,
            text=text,
            workaround=workaround,
            tags=tags,
            author_actor_id=author_actor_id,
            expires_at=expires_at,
            propagate_to_children=propagate_to_children,
            parent_id=parent_id,
        ):
            _ = state  # CautionRegistered is the genesis event; prior state ignored
            return Caution(
                id=caution_id,
                target=target,
                category=CautionCategory(category),
                severity=CautionSeverity(severity),
                text=CautionText(text),
                workaround=CautionWorkaround(workaround),
                author_actor_id=author_actor_id,
                tags=frozenset(CautionTag(t) for t in tags),
                expires_at=expires_at,
                propagate_to_children=propagate_to_children,
                status=CautionStatus.ACTIVE,
                parent_id=parent_id,
            )
        case CautionSuperseded(superseded_by_caution_id=superseded_by_caution_id):
            prior = require_state(state, "CautionSuperseded")
            return Caution(
                id=prior.id,
                target=prior.target,
                category=prior.category,
                severity=prior.severity,
                text=prior.text,
                workaround=prior.workaround,
                author_actor_id=prior.author_actor_id,
                tags=prior.tags,
                expires_at=prior.expires_at,
                propagate_to_children=prior.propagate_to_children,
                status=CautionStatus.SUPERSEDED,
                parent_id=prior.parent_id,
                superseded_by_caution_id=superseded_by_caution_id,
                retired_reason=prior.retired_reason,
            )
        case CautionRetired(reason=reason):
            prior = require_state(state, "CautionRetired")
            return Caution(
                id=prior.id,
                target=prior.target,
                category=prior.category,
                severity=prior.severity,
                text=prior.text,
                workaround=prior.workaround,
                author_actor_id=prior.author_actor_id,
                tags=prior.tags,
                expires_at=prior.expires_at,
                propagate_to_children=prior.propagate_to_children,
                status=CautionStatus.RETIRED,
                parent_id=prior.parent_id,
                superseded_by_caution_id=prior.superseded_by_caution_id,
                retired_reason=CautionRetireReason(reason),
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CautionEvent]) -> Caution | None:
    """Replay a stream of events from the empty initial state."""
    state: Caution | None = None
    for event in events:
        state = evolve(state, event)
    return state
