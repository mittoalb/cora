"""Property-based tests for the Actor evolver + replay determinism.

The canonical event-sourcing property: `fold(events) -> state` is
deterministic and stable across replays. For the Actor aggregate
(post PII vault):

  - evolve(None, ActorRegistered) → Actor with is_active=True and
    id / kind from the event. Display name lives outside the
    aggregate in the actor_profile vault.
  - evolve(active_actor, ActorDeactivated) → same actor with
    is_active=False (id / kind preserved).
  - fold([register, deactivate]) is inactive; fold([register]) is
    active. Same events fold to the same state every time (purity).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from cora.access.aggregates.actor import (
    Actor,
    ActorDeactivated,
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor.evolver import evolve, fold

_KIND = st.sampled_from(list(ActorKind))
_DATETIME = st.datetimes()


@pytest.mark.unit
@given(actor_id=st.uuids(), kind=_KIND, occurred_at=_DATETIME)
def test_evolve_registered_from_none_yields_active_actor(
    actor_id: UUID, kind: ActorKind, occurred_at: datetime
) -> None:
    """First-event fold: state is exactly the event fields, is_active=True."""
    state = evolve(None, ActorRegistered(actor_id=actor_id, occurred_at=occurred_at, kind=kind))
    assert state == Actor(id=actor_id, is_active=True, kind=kind)


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    kind=_KIND,
    registered_at=_DATETIME,
    deactivated_at=_DATETIME,
)
def test_evolve_deactivated_flips_is_active_preserves_rest(
    actor_id: UUID,
    kind: ActorKind,
    registered_at: datetime,
    deactivated_at: datetime,
) -> None:
    """Deactivation flips is_active=False; id / kind preserved."""
    active = evolve(
        None,
        ActorRegistered(actor_id=actor_id, occurred_at=registered_at, kind=kind),
    )
    inactive = evolve(active, ActorDeactivated(actor_id=actor_id, occurred_at=deactivated_at))
    assert inactive == Actor(id=actor_id, is_active=False, kind=kind)


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    kind=_KIND,
    registered_at=_DATETIME,
    deactivated_at=_DATETIME,
)
def test_fold_is_deterministic_across_replays(
    actor_id: UUID,
    kind: ActorKind,
    registered_at: datetime,
    deactivated_at: datetime,
) -> None:
    """Replay determinism: same event list folds to the same state every time.
    This is THE event-sourcing property — if it ever stops holding, projections
    silently diverge across replicas.
    """
    events = [
        ActorRegistered(actor_id=actor_id, occurred_at=registered_at, kind=kind),
        ActorDeactivated(actor_id=actor_id, occurred_at=deactivated_at),
    ]
    first_replay = fold(events)
    second_replay = fold(events)
    assert first_replay == second_replay
    assert first_replay is not None
    assert first_replay.is_active is False
