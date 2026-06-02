"""Typed `RecipeStep` union and wire-format helpers for Recipe step bodies.

A `Recipe` carries an ordered tuple of `RecipeStep` instances that
expands to a flat sequence of Conductor `Step`s when an operator
binds parameter values via the `register_procedure_from_recipe`
slice (Operation BC). This module ships the type vocabulary and the
wire-format round-trip; the `expand` function that consumes these
VOs into Operation BC `Step`s lives in `cora.operation._recipe_expansion`
because the dependency direction is Operation -> Recipe (Recipe must
not depend on Operation per BC isolation enforced by tach).

## Substitution shape: typed `BindingRef`, not textual `${var}`

Three-pass corpus research established that production beamline and
factory automation systems use typed structures, not textual
interpolation. CORA's codebase convention is frozen dataclasses for
domain models, so `BindingRef(name="dwell")` is a structurally
distinct sentinel from the string `"dwell"`: a literal address
`"2bma:rot:val"` is just a `str`; a binding reference is a
`BindingRef`. The expansion function dispatches on
`isinstance(value, BindingRef)`.

## v1 scope: values bind, addresses do not

Each deployment's Recipe HARDCODES its PV addresses and only
parameterizes operator-tunable VALUES (dwell, repetitions,
angle_start, etc.). At v1 the parameterized positions are:

  - `RecipeSetpointStep.value`
  - `RecipeActionStep.params` (per-key values)
  - `RecipeCheckStep.criterion` thresholds stay literal at v1
    (operators do not tune pass/fail; the criterion is part of the
    Recipe contract)

Addresses + action-body `name` + check-step criterion shapes stay
LITERAL. A v2 trigger to widen address-binding fires when a
deployment ships two near-identical Recipes that differ only in PV
prefix.

## Criterion carrier shape

`RecipeCheckStep.criterion` is a dict-shaped wire payload (the same
`{kind: ..., expected: ...}` shape the Conductor uses for its
CheckStep criterion serialization). The translation to the typed
`EqualsCriterion | WithinToleranceCriterion` union happens in
`cora.operation._recipe_expansion.expand`. This keeps Recipe BC free
of any Operation BC import.

## No `RecipeBody` wrapper VO

Non-emptiness on the step sequence is enforced inside
`Recipe.__post_init__`, not by a wrapper carrier. `to_dict` and
`from_dict` operate on `tuple[RecipeStep, ...]` directly.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast


@dataclass(frozen=True)
class BindingRef:
    """Sentinel value: substitute with `bindings[name]` at expansion time.

    `name` must match a property name in the referenced
    `Capability.parameters_schema`. Binding-reference validation lives
    in the define-recipe-time decider (and re-runs at version_recipe
    and expansion time per [[project-recipe-aggregate-design]] Locks);
    this VO carries the reference shape only.
    """

    name: str


@dataclass(frozen=True)
class RecipeSetpointStep:
    """Setpoint step template: `value` may be a literal or a `BindingRef`.

    `address` is hardcoded per Recipe (no parameterization at v1 per
    the v1 scope note in the module docstring); `value` is the only
    bindable position. `verify` mirrors `SetpointStep.verify` exactly.
    """

    address: str
    value: int | float | bool | str | tuple[Any, ...] | BindingRef
    verify: bool = False


@dataclass(frozen=True)
class RecipeActionStep:
    """Action step template: each `params` value may be a literal or `BindingRef`.

    `name` is the registered action-body name; not parameterized.
    `params` values may individually be `BindingRef` sentinels; the
    expansion function walks the mapping and substitutes per-key.
    """

    name: str
    params: Mapping[str, Any | BindingRef] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class RecipeCheckStep:
    """Check step template: `criterion` is the wire-format dict.

    Carrying the criterion as a `{kind: ..., expected: ..., tolerance?: ...}`
    dict lets Recipe BC define the step VO without importing the typed
    criterion classes from Operation BC. The expansion function in
    `cora.operation._recipe_expansion` translates the dict to the typed
    `EqualsCriterion | WithinToleranceCriterion` union at runtime.

    Recognized kinds today: `"equals"`, `"within_tolerance"`. The
    expansion function raises `ValueError` for unknown kinds.
    """

    address: str
    criterion: Mapping[str, Any]


RecipeStep = RecipeSetpointStep | RecipeActionStep | RecipeCheckStep
"""Closed discriminated union of templated step shapes; parallels `Step` arm-for-arm."""


class UnboundRecipeBindingError(Exception):
    """A `BindingRef.name` did not resolve in the supplied `bindings` mapping.

    Family: `Invalid<X>`. The central REST handler maps this to HTTP 422.
    Renamed from the worktree's `UnboundBindingError` as part of the
    Recipe rename pass.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"unbound binding reference: {name!r}")
        self.name = name


class InvalidRecipeStepShapeError(Exception):
    """Wire-format dict could not be parsed into a `RecipeStep`.

    Raised by `from_dict` for unknown step kinds, missing required
    keys, or structurally malformed payloads. Family: `Invalid<X>`.
    HTTP 422 (parse failure after Pydantic boundary).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"recipe step wire shape invalid: {reason}")
        self.reason = reason


_BINDING_KEY = "__binding__"
"""Wire-format key distinguishing a `BindingRef` from a literal dict value.

A literal `dict` value in `params` MUST NOT carry this key at v1; the
wire format does not currently support escaping. If a future deployment
needs to bind a dict-typed parameter that happens to carry this exact
key, widen the escape rule then (no current consumer)."""


def _value_to_wire(value: Any | BindingRef) -> Any:
    """Serialize one value (literal or BindingRef) to a JSON-friendly form."""
    if isinstance(value, BindingRef):
        return {_BINDING_KEY: value.name}
    return value


def _value_from_wire(value: Any) -> Any:
    """Deserialize one wire value; reconstruct BindingRef from sentinel dict.

    Returns either the original value (literal) or a `BindingRef`
    instance. Signature widens to `Any` because callers store the
    result into mappings whose value-type is also `Any`; narrowing to
    `Any | BindingRef` does not help downstream type-checking.
    """
    if isinstance(value, dict):
        typed = cast("dict[str, Any]", value)
        if set(typed.keys()) == {_BINDING_KEY}:
            return BindingRef(name=typed[_BINDING_KEY])
    return cast("Any", value)


def _step_to_wire(step: RecipeStep) -> dict[str, Any]:
    if isinstance(step, RecipeSetpointStep):
        return {
            "kind": "setpoint",
            "address": step.address,
            "value": _value_to_wire(step.value),
            "verify": step.verify,
        }
    if isinstance(step, RecipeActionStep):
        return {
            "kind": "action",
            "name": step.name,
            "params": {key: _value_to_wire(val) for key, val in step.params.items()},
        }
    return {
        "kind": "check",
        "address": step.address,
        "criterion": dict(step.criterion),
    }


def _step_from_wire(payload: dict[str, Any]) -> RecipeStep:
    try:
        kind = payload["kind"]
    except (KeyError, TypeError) as exc:
        raise InvalidRecipeStepShapeError("step missing 'kind'") from exc
    try:
        if kind == "setpoint":
            return RecipeSetpointStep(
                address=payload["address"],
                value=_value_from_wire(payload["value"]),
                verify=payload.get("verify", False),
            )
        if kind == "action":
            return RecipeActionStep(
                name=payload["name"],
                params={key: _value_from_wire(val) for key, val in payload["params"].items()},
            )
        if kind == "check":
            return RecipeCheckStep(
                address=payload["address"],
                criterion=dict(payload["criterion"]),
            )
    except (KeyError, AttributeError, TypeError) as exc:
        raise InvalidRecipeStepShapeError(f"step kind {kind!r}: {exc}") from exc
    raise InvalidRecipeStepShapeError(f"unknown recipe step kind: {kind!r}")


def to_dict(steps: tuple[RecipeStep, ...]) -> dict[str, Any]:
    """Serialize a Recipe step sequence to a JSON-friendly dict for event storage.

    Returns a wrapper dict with a single `steps` list, mirroring the
    worktree wire format. Callers store the result directly in a
    `RecipeDefined` or `RecipeVersioned` payload.
    """
    return {"steps": [_step_to_wire(step) for step in steps]}


def from_dict(payload: dict[str, Any]) -> tuple[RecipeStep, ...]:
    """Rebuild a Recipe step sequence from its wire-format dict.

    Returns `tuple[RecipeStep, ...]` directly; does NOT enforce
    non-emptiness (that invariant is carried by `Recipe.__post_init__`
    when the steps are folded into a `Recipe(...)` instance).

    Raises `InvalidRecipeStepShapeError` for unknown step kinds or
    structurally malformed payloads.
    """
    try:
        raw_steps = payload["steps"]
    except (KeyError, TypeError) as exc:
        raise InvalidRecipeStepShapeError("payload missing 'steps'") from exc
    return tuple(_step_from_wire(s) for s in raw_steps)


def resolve_value(value: Any | BindingRef, bindings: Mapping[str, Any]) -> Any:
    """Resolve a single value (literal or BindingRef) against `bindings`.

    Public helper the Operation BC `expand` function uses to substitute
    one value at a time without duplicating the BindingRef-aware lookup
    logic. Raises `UnboundRecipeBindingError` when a BindingRef name is
    missing from `bindings`.
    """
    if isinstance(value, BindingRef):
        if value.name not in bindings:
            raise UnboundRecipeBindingError(value.name)
        return bindings[value.name]
    return value


__all__ = [
    "BindingRef",
    "InvalidRecipeStepShapeError",
    "RecipeActionStep",
    "RecipeCheckStep",
    "RecipeSetpointStep",
    "RecipeStep",
    "UnboundRecipeBindingError",
    "from_dict",
    "resolve_value",
    "to_dict",
]
