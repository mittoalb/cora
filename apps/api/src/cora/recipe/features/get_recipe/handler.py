"""Application handler for the `get_recipe` query slice.

Path C: handler returns RecipeView bundling aggregate state +
projection-sourced lifecycle timestamps. State stays minimal per
decider purity; timestamps live on the projection per the May-2026
template-aggregate-timestamps sweep. Mirrors the pattern from
Capability / Method / Plan / Practice / Family.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeLifecycleTimestamps,
    load_recipe,
    load_recipe_timestamps,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_recipe.query import GetRecipe

_QUERY_NAME = "GetRecipe"

_log = get_logger(__name__)


@dataclass(frozen=True)
class RecipeView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection has not caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode)."""

    recipe: Recipe
    timestamps: RecipeLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_recipe handler implements."""

    async def __call__(
        self,
        query: GetRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RecipeView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_recipe handler closed over the shared deps."""

    async def handler(
        query: GetRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RecipeView | None:
        _log.info(
            "get_recipe.start",
            query_name=_QUERY_NAME,
            recipe_id=str(query.recipe_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_recipe.denied",
                query_name=_QUERY_NAME,
                recipe_id=str(query.recipe_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        recipe = await load_recipe(deps.event_store, query.recipe_id)
        if recipe is None:
            _log.info(
                "get_recipe.success",
                query_name=_QUERY_NAME,
                recipe_id=str(query.recipe_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: RecipeLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_recipe_timestamps(deps.pool, query.recipe_id)

        _log.info(
            "get_recipe.success",
            query_name=_QUERY_NAME,
            recipe_id=str(query.recipe_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return RecipeView(recipe=recipe, timestamps=timestamps)

    return handler
