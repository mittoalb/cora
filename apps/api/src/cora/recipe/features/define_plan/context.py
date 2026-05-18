"""Cross-aggregate context the `define_plan` decider validates against.

`PlanBindingContext` is built by the `define_plan` handler from
`load_practice` + `load_method` + `load_asset` calls before reaching
the pure decider. The decider treats these loaded entities as
opaque domain data and validates the binding without performing
any I/O.

Per gate-review Q5: this is the canonical pattern for any future
decider that needs cross-aggregate state. The handler (impure
shell) loads what's needed; the decider (pure core) receives it as
plain values. Keeps the decider referentially transparent — same
inputs, same outputs, no need to mock loaders in unit tests.

Slice-local module by design: only `define_plan` uses it today.
Sibling pattern: `cora.run.features.start_run.context.RunStartContext`
(6f-1) holds Plan + Subject (optional) + assets — same shape, slice-
specific entities. Each cross-validating slice produces its own
context dataclass; promote to a shared form only after the Rule of
Three.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.recipe.aggregates.method import Method
from cora.recipe.aggregates.practice import Practice


@dataclass(frozen=True)
class PlanBindingContext:
    """Snapshot of upstream aggregate state at Plan-bind time.

    `practice` and `method` are the two recipe-ladder ancestors the
    Plan binds (Practice always, Method via `practice.method_id`).
    `assets` is the loaded set of bound Asset instances keyed by
    their id.

    All three carry their own status / lifecycle fields so the
    decider can reject Deprecated / Decommissioned upstreams. The
    capability-superset check uses each Asset's `capabilities` and
    the Method's `needed_families` (gate-review Q3: bound-Asset-
    only, no hierarchy walk).
    """

    practice: Practice
    method: Method
    assets: dict[UUID, Asset]
