# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Read repositories for the Recipe aggregate.

`load_recipe(event_store, recipe_id) -> Recipe | None` mirrors
`load_capability` / `load_method` / `load_plan`.

`load_recipe_timestamps(pool, recipe_id) -> RecipeLifecycleTimestamps | None`
reads the projection-row metadata that mirrors the FSM transitions
(Path C). State stays minimal per decider purity; lifecycle
timestamps live on the projection per the May-2026
template-aggregate-timestamps sweep precedent. Mirrors
`load_capability_timestamps` / `load_method_timestamps` /
`load_plan_timestamps` / `load_practice_timestamps` /
`load_family_timestamps`.

Note: `Recipe.replaced_by_recipe_id` STATE field is unaffected; it's
an intrinsic deprecation pointer the decider may read on future
commands, distinct from the lifecycle-when timestamp surfaced here.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.recipe.events import (
    RecipeVersioned,
    from_stored,
)
from cora.recipe.aggregates.recipe.evolver import fold
from cora.recipe.aggregates.recipe.state import (
    Recipe,
    RecipeVersionNotFoundError,
)

_STREAM_TYPE = "Recipe"

_SELECT_TIMESTAMPS_SQL = """
SELECT created_at, versioned_at, deprecated_at
FROM proj_recipe_recipe_summary
WHERE recipe_id = $1
"""


@dataclass(frozen=True)
class RecipeLifecycleTimestamps:
    """Observed wall-clock timestamps of FSM transitions.

    Sourced from the Recipe summary projection, not from aggregate
    state. `created_at` is set once on `RecipeDefined`; `versioned_at`
    is overwritten on each `RecipeVersioned` (state-always-holds-latest
    convention mirrored in the projection); `deprecated_at` is set
    once on `RecipeDeprecated` and is terminal.
    """

    created_at: datetime
    versioned_at: datetime | None
    deprecated_at: datetime | None


async def load_recipe(event_store: EventStore, recipe_id: UUID) -> Recipe | None:
    """Load and fold a Recipe's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, recipe_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_recipe_at_version(
    event_store: EventStore,
    recipe_id: UUID,
    version_tag: str | None,
) -> Recipe | None:
    """Load Recipe state at the pinned `version_tag` (first-match-from-head).

    Walks the Recipe event stream from genesis, folding events into
    `Recipe` state incrementally. Stops AT the first `RecipeVersioned`
    event whose `version_tag` matches the pinned tag and returns the
    post-fold state. Used by `conduct_procedure` replay (per
    [[project-run-procedure-replay-design]]) to resolve a Recipe to
    the exact snapshot pinned in `RecipeExpansionRecorded.recipe_version`.

    Semantics:
    - Returns `None` when the Recipe stream is empty (no genesis event);
      the caller decides whether to raise.
    - When `version_tag is None`, returns the post-genesis state
      (post-`RecipeDefined`, no `version_recipe` calls yet). This
      mirrors `Recipe.version is None` and covers Procedures registered
      from a Recipe that was never versioned.
    - When `version_tag` is set and the stream has events but no
      `RecipeVersioned` matches, raises `RecipeVersionNotFoundError`.
    - First-match-from-head when multiple `RecipeVersioned` events
      share a tag (re-tagging is allowed per ): the first
      match wins because the later re-tagging cannot retroactively
      change which version was pinned by an earlier
      `RecipeExpansionRecorded`.
    - The fold runs over all preceding events; `RecipeDeprecated`
      events the FSM forbids ahead of a matching `RecipeVersioned`
      are still folded defensively (the helper does not assume FSM
      cleanliness, only that it can find the target event).
    """
    stored, _version = await event_store.load(_STREAM_TYPE, recipe_id)
    if not stored:
        return None
    events = [from_stored(s) for s in stored]
    if version_tag is None:
        return fold(events[:1])
    for index, event in enumerate(events):
        if isinstance(event, RecipeVersioned) and event.version_tag == version_tag:
            return fold(events[: index + 1])
    raise RecipeVersionNotFoundError(recipe_id, version_tag)


async def load_recipe_timestamps(
    pool: asyncpg.Pool,
    recipe_id: UUID,
) -> RecipeLifecycleTimestamps | None:
    """Read the lifecycle-timestamp triple from the projection.

    Contract: `pool` MUST be a live asyncpg pool; None-check belongs
    to the caller, not this function (mirrors `load_capability_timestamps`
    and peers).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_TIMESTAMPS_SQL, recipe_id)
    if row is None:
        return None
    return RecipeLifecycleTimestamps(
        created_at=row["created_at"],
        versioned_at=row["versioned_at"],
        deprecated_at=row["deprecated_at"],
    )
