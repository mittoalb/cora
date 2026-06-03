"""RecipeExpansionPort: pure function from Recipe step tuple + bindings to Step tuple.

Per [[project-recipe-aggregate-design]] the expansion is a PURE function:
no clock, no port I/O, no randomness, no module-global state. The port
carries a `version` attribute so `RecipeExpansionRecorded` provenance
events capture which expander emitted a given expansion, enabling
replay even if a deployment later swaps the default for a custom
expander.

The default adapter (`InMemoryRecipeExpansionPort`) delegates to the
pure `expand` function in `cora.operation._recipe_expansion`. Future
custom expanders (a deployment-specific DSL or a memoizing cache)
implement the same Protocol and ship their own `version` string.

Errors propagate unchanged: `UnboundRecipeBindingError` (from Recipe BC)
when a `BindingRef.name` is missing from `bindings`; `ValueError` for
unknown criterion kinds in a check step.

## 2-arg pure-substitution contract

Schema validation does NOT belong on this port. BindingRef-vs-schema
integrity lives in `cora.recipe.aggregates.recipe.steps_validation`
(called by the slice handler before expansion); operator-binding-value
shape validation lives in the slice decider via
`validate_values_against_schema` (raises `InvalidRecipeBindingsError`).
The port is pure substitution + ordering of typed Step VOs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.conductor import Step
    from cora.recipe.aggregates.recipe import RecipeStep


@runtime_checkable
class RecipeExpansionPort(Protocol):
    """Pure expansion of a Recipe's step tuple to a Conductor `Step` tuple.

    `version` is a stable string identifying the expander (default impl
    pins to `"v1"`). Provenance events capture `version` so the same
    `(steps, bindings)` inputs reproduce the same outputs even after a
    deployment swaps expanders.
    """

    @property
    def version(self) -> str: ...

    def expand(
        self, steps: tuple[RecipeStep, ...], bindings: Mapping[str, Any]
    ) -> tuple[Step, ...]: ...


__all__ = ["RecipeExpansionPort"]
