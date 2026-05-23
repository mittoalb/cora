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
holds Plan + Subject (optional) + assets, same shape, slice-
specific entities. Each cross-validating slice produces its own
context dataclass; promote to a shared form only after the Rule of
Three.
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import Capability
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
    family-superset check uses each Asset's `families` and
    the Method's `needed_families` (gate-review Q3: bound-Asset-
    only, no hierarchy walk).

    Cross-BC affordance-cover additive: `capability` and
    `family_affordances` carry the Capability template + per-Family
    affordance summaries needed
    for the affordance-cover guard.

    - `capability` is the universal Capability template the bound
      Method realizes (loaded via `method.capability_id`). None when
      Method has no `capability_id` (legacy shape), in that
      case the decider SKIPS the affordance-cover guard entirely.
    - `family_affordances` maps Family.id → that Family's `affordances`
      set. The handler loads every Family referenced by any bound
      Asset's `families` set. Empty dict when `capability is None`
      (no point loading Families if we won't validate them).

    The decider unions `family_affordances` across `asset.families`
    and asserts the union covers `capability.required_affordances`.
    """

    practice: Practice
    method: Method
    assets: dict[UUID, Asset]
    capability: Capability | None = None
    family_affordances: dict[UUID, frozenset[Affordance]] = field(
        default_factory=dict[UUID, frozenset[Affordance]]
    )
