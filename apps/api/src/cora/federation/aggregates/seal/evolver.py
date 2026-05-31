"""Evolver: replay events to reconstruct Seal state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `SealEvent` without a matching match arm here.

Status mapping per event type:

  - `SealInitialized` produces LIVE (genesis; sequence 0, no
    head hash yet).
  - `SealPointerSigned` keeps LIVE (head hash and sequence
    refreshed; `last_signed_*` lives on projection per Path C).
  - `SealOnlineKeyRotated` keeps LIVE (online_key_ref swapped;
    offline unchanged).
  - `SealRepublishingStarted` moves to REPUBLISHING.
  - `SealRepublishingCompleted` returns to LIVE (head hash and
    sequence refreshed).

Per Path C ([[project_template_aggregate_timestamps]]), aggregate
state carries no lifecycle bookkeeping timestamps; both
`initialized_at` and `last_signed_at` live on the projection,
populated from event envelope `occurred_at` and from the
`SealPointerSigned.signed_at` payload field respectively.

Source-state guards and key-separation checks live at the decider,
NOT here; the evolver trusts the event log (folded events have
already passed their decider). The `_key_separation` helper module
exists so transition deciders can invoke it before commit.

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.federation.aggregates.seal.events import (
    SealEvent,
    SealInitialized,
    SealOnlineKeyRotated,
    SealPointerSigned,
    SealRepublishingCompleted,
    SealRepublishingStarted,
)
from cora.federation.aggregates.seal.state import (
    Seal,
    SealStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Seal | None, event: SealEvent) -> Seal:
    """Apply one event to the current state."""
    match event:
        case SealInitialized(
            facility_id=facility_id,
            online_key_ref=online_key_ref,
            offline_key_ref=offline_key_ref,
            initialized_by_actor_id=initialized_by_actor_id,
        ):
            _ = state  # SealInitialized is the genesis event; prior state ignored
            return Seal(
                facility_id=facility_id,
                online_key_ref=online_key_ref,
                offline_key_ref=offline_key_ref,
                current_head_hash=None,
                current_sequence_number=0,
                initialized_by_actor_id=initialized_by_actor_id,
                status=SealStatus.LIVE,
            )
        case SealPointerSigned(
            head_hash=head_hash,
            sequence_number=sequence_number,
        ):
            prior = require_state(state, "SealPointerSigned")
            return Seal(
                facility_id=prior.facility_id,
                online_key_ref=prior.online_key_ref,
                offline_key_ref=prior.offline_key_ref,
                current_head_hash=head_hash,
                current_sequence_number=sequence_number,
                initialized_by_actor_id=prior.initialized_by_actor_id,
                status=SealStatus.LIVE,
            )
        case SealOnlineKeyRotated(new_online_key_ref=new_online_key_ref):
            prior = require_state(state, "SealOnlineKeyRotated")
            return Seal(
                facility_id=prior.facility_id,
                online_key_ref=new_online_key_ref,
                offline_key_ref=prior.offline_key_ref,
                current_head_hash=prior.current_head_hash,
                current_sequence_number=prior.current_sequence_number,
                initialized_by_actor_id=prior.initialized_by_actor_id,
                status=SealStatus.LIVE,
            )
        case SealRepublishingStarted():
            prior = require_state(state, "SealRepublishingStarted")
            return Seal(
                facility_id=prior.facility_id,
                online_key_ref=prior.online_key_ref,
                offline_key_ref=prior.offline_key_ref,
                current_head_hash=prior.current_head_hash,
                current_sequence_number=prior.current_sequence_number,
                initialized_by_actor_id=prior.initialized_by_actor_id,
                status=SealStatus.REPUBLISHING,
            )
        case SealRepublishingCompleted(
            new_head_hash=new_head_hash,
            new_sequence_number=new_sequence_number,
        ):
            prior = require_state(state, "SealRepublishingCompleted")
            return Seal(
                facility_id=prior.facility_id,
                online_key_ref=prior.online_key_ref,
                offline_key_ref=prior.offline_key_ref,
                current_head_hash=new_head_hash,
                current_sequence_number=new_sequence_number,
                initialized_by_actor_id=prior.initialized_by_actor_id,
                status=SealStatus.LIVE,
            )
        case _:  # pragma: no cover
            assert_never(event)


def fold(events: Sequence[SealEvent]) -> Seal | None:
    """Replay a stream of events from the empty initial state."""
    state: Seal | None = None
    for event in events:
        state = evolve(state, event)
    return state
