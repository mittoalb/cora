"""Compose the Recipe BC's handlers from `SharedDeps`.

`wire_recipe(deps)` is invoked once from the FastAPI lifespan and
the returned `RecipeHandlers` bundle is stored on
`app.state.recipe`. Routes and MCP tools pull their handler out of
that bundle. New slices (commands or queries) add a new field on
`RecipeHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment (composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

Phase 6a ships `define_method` + `get_method`. Subsequent phases:
  - 6b: Method transitions (version, deprecate)
  - 6c: Method enrichment (description, owner)
  - 6d: Practice aggregate slices
  - 6e: Plan aggregate slices (depends on 5f Asset.capabilities)
  - 6f: Run aggregate slices
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing
from cora.recipe.features import (
    define_method,
    get_method,
)

_BC = "recipe"


@dataclass(frozen=True)
class RecipeHandlers:
    """The Recipe BC's handler bundle, each closed over SharedDeps.

    Phase 6a ships `define_method` (create-style; idempotency-
    wrapped) and `get_method` (read side). Subsequent slices
    (transitions, Practice, Plan, Run) land per-phase.
    """

    define_method: define_method.IdempotentHandler
    get_method: get_method.Handler


def wire_recipe(deps: SharedDeps) -> RecipeHandlers:
    """Build the Recipe BC handlers from shared dependencies."""
    return RecipeHandlers(
        define_method=with_tracing(
            with_idempotency(
                define_method.bind(deps),
                deps.idempotency_store,
                command_name="DefineMethod",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="DefineMethod",
            bc=_BC,
        ),
        get_method=with_tracing(
            get_method.bind(deps),
            command_name="GetMethod",
            bc=_BC,
            kind="query",
        ),
    )
