"""The `DefinePlan` command — intent dataclass for this slice.

Carries the caller-controlled inputs:
  - `name` — display name for the new Plan
  - `practice_id` — the Practice this Plan binds (eventual-
    consistency ref; existence verified at handler-load time)
  - `asset_ids` — the set of Assets this Plan binds (multi-asset;
    at least one required, validated at decide time)

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports.

Status is implicit at definition (`Defined`) and not part of the
command — see Plan aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.

The handler additionally pre-loads Practice → Method → each Asset
to build a `PlanBindingContext` for the decider (gate-review Q5
pattern). Existence misses become `<X>NotFoundError`; state-of-
existing-thing checks happen in the decider.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DefinePlan:
    """Define a new Plan: bind a Practice to a set of Asset instances."""

    name: str
    practice_id: UUID
    asset_ids: frozenset[UUID]
