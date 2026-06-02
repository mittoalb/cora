"""Default `RecipeExpansionPort` adapter: pure delegation to `expand`.

Wraps the module-level `cora.operation._recipe_expansion.expand` function
in a Protocol-conforming object and pins a stable `version` string. The
version is recorded in `RecipeExpansionRecorded` provenance events so
replay can verify which expander produced a given step sequence.

A new expander version is a code change here: bump `version` to the
next stable tag when expansion semantics change in a way that affects
already-recorded provenance events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.conductor import Step
    from cora.recipe.aggregates.recipe import RecipeStep

_DEFAULT_VERSION = "v1"


@dataclass(frozen=True)
class InMemoryRecipeExpansionPort:
    """Pure-function `RecipeExpansionPort` backed by the default `expand`.

    `version` defaults to `"v1"` and is rarely overridden in production;
    tests pass a different version when they need to assert provenance
    carries the expander identity.
    """

    version: str = _DEFAULT_VERSION

    def expand(
        self, steps: tuple[RecipeStep, ...], bindings: Mapping[str, Any]
    ) -> tuple[Step, ...]:
        from cora.operation._recipe_expansion import expand as _expand

        return _expand(steps, bindings)


__all__ = ["InMemoryRecipeExpansionPort"]
