"""Cross-aggregate context the `start_run` decider validates against.

`RunStartContext` is built by the `start_run` handler from
`load_plan` + `load_subject` (if subject_id given) + `load_asset`
calls before reaching the pure decider. The decider treats these
loaded entities as opaque domain data and validates the Run-start
preconditions without performing any I/O.

Per gate-review Q2 / Q5: this is the canonical pattern for cross-
aggregate validation in CORA, mirroring `PlanBindingContext` from
6e-1 (the first decider that took cross-aggregate state as input).
Documented in CONTRIBUTING.md as the cross-aggregate-validation
idiom for any future cross-validating decider.

Slice-local module by design: only `start_run` uses it today.

## Field semantics

  - `plan`: the Plan being executed. Decider rejects if Deprecated.
  - `subject`: the Subject being measured, or None for dark-field /
    flat-field calibration runs (per beamline-domain convention).
    Decider rejects if non-None and not in Mounted | Measured.
  - `assets`: dict keyed by asset_id, loaded from `plan.asset_ids`.
    Decider rejects if any is Decommissioned, and re-validates
    capability superset against current Asset state (drift since
    Plan-bind is real; Run is the last gate).

Naming: `assets` (not `bound_assets`) matches `PlanBindingContext`
precedent. The "bound" qualifier was meaningful at Plan-bind time
(Plan was doing the binding); at Run-start, Run isn't binding
anything new.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.recipe.aggregates.plan import Plan
from cora.subject.aggregates.subject import Subject


@dataclass(frozen=True)
class RunStartContext:
    """Snapshot of upstream aggregate state at Run-start time.

    `subject` is None when the Run has no Subject (calibration /
    dark-field run). `assets` is loaded from `plan.asset_ids`.
    """

    plan: Plan
    subject: Subject | None
    assets: dict[UUID, Asset]
