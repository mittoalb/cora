"""Plan aggregate state, value objects, status enum, and domain errors.

`Plan` is the recipe ladder's binding layer (ISA-88 Master/Control
Recipe analog). A Plan binds a `Practice` (which itself adapts a
`Method` for a site) to a specific set of `Asset` instances at the
facility. Plan is what `Run` ultimately executes.

Per the BC map's recipe ladder: Method (≈ General Recipe, equipment-
agnostic) → Practice (≈ Site Recipe, facility-localized) → Plan
(≈ Master/Control Recipe, equipment-bound) → Run (≈ batch execution).

## Aggregate scope

Plan state:
  - `id` + `name`
  - `practice_id: UUID` — the Practice this Plan binds (eventual-
    consistency ref; existence verified at handler-load time, not
    in the decider)
  - `asset_ids: frozenset[UUID]` — the Assets this Plan is bound
    to (multi-asset binding; gate-review Q3)
  - `status: PlanStatus` (Defined → Versioned → Deprecated FSM)
  - `version: str | None` — operator-supplied label of the most
    recent `version_plan` call (None until first version)

Phase history: 6e-1 shipped scaffold + `define_plan` + `get_plan`;
6e-2 added the `version` field with `version_plan` + `deprecate_plan`
transitions (matches Method 6a→6b and Practice 6d-1→6d-2 precedent
of adding fields when the first mutating event arrives, not
speculatively).

Audit data captured at bind time (`method_id`, snapshots of the
Method's needs_capabilities and each bound Asset's capabilities)
lives in the `PlanDefined` event payload only — NOT in state.
Slim Aggregate principle (gate-review Q4): state holds only what
future deciders need to validate invariants. version_plan and
deprecate_plan don't re-validate capabilities, so the snapshots
stay payload-only.

Additional facets defer to a 6e-3+ sub-phase if pilot demand emerges:
  - `wiring` (which Asset.ports are connected to what; depends on
    Asset.ports landing first, currently 5f+ deferred)
  - calibrations
  - per-Plan parameter overrides

## Cross-aggregate validation at bind time (gate-review Q5)

The `define_plan` handler pre-loads Practice, Method (via
`practice.method_id`), and each bound Asset, then hands the loaded
entities to the pure decider as a `PlanBindingContext`. The decider
treats them as opaque domain data and validates:

  - Practice not Deprecated → `PracticeDeprecatedError`
  - Method not Deprecated → `MethodDeprecatedError`
  - No bound Asset is Decommissioned → `AssetDecommissionedError`
  - `union(asset.capabilities) ⊇ method.needs_capabilities` →
    `PlanCapabilitiesNotSatisfiedError`

Handler-side load misses become `PracticeNotFoundError` /
`MethodNotFoundError` / `AssetNotFoundError` (defined on the
respective aggregates) before reaching the decider. The four
errors above are Plan-domain errors specific to "you tried to bind
to something whose state forbids binding"; they live in this
module.

This is the first decider in the codebase that takes cross-
aggregate state as input. The pattern is documented in
CONTRIBUTING.md as the canonical approach for future cross-
validating deciders (Run will follow the same shape).

## Status as enum-in-state, derived-from-event-type-in-evolver

Same precedent as Method (6a) and Practice (6d-1) and Capability
(5a). The lifecycle mirrors theirs: Defined → Versioned →
Deprecated. Approval/governance is a separate concern handled by
the future Decision BC with `RecipeApproval` context (gate-review
Q2).

## Tenth bounded-name VO + helper extraction

`PlanName` is the **tenth** bounded-name VO. The 5a gate-review
parked extraction at "first per-VO divergence OR ~10 instances".
We hit 10 with no divergence pressure, so the trim+length-check
helper got hoisted to `cora.infrastructure.name.validate_name`
(see that module's docstring). PlanName uses the helper from day
one; the prior 9 VOs were refactored in the same 6e-1 commit.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.name import validate_name

PLAN_NAME_MAX_LENGTH = 200
PLAN_VERSION_TAG_MAX_LENGTH = 50


class PlanStatus(StrEnum):
    """The Plan's lifecycle state.

    Mirrors Method's and Practice's lifecycle (and Capability's).
    Transitions land per-slice in Phase 6e-2:
      - Defined -> Versioned        (version_plan)
      - (Defined | Versioned) -> Deprecated  (deprecate_plan)

    `Defined` is the genesis state set by `define_plan`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidPlanNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Plan name must be 1-{PLAN_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidPlanError(ValueError):
    """The supplied DefinePlan command violates a structural invariant.

    Currently raised when `asset_ids` is empty (a Plan must bind at
    least one Asset; gate-review locked this as a domain invariant).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid plan: {reason}")
        self.reason = reason


class PlanAlreadyExistsError(Exception):
    """Attempted to define a plan whose stream already has events."""

    def __init__(self, plan_id: UUID) -> None:
        super().__init__(f"Plan {plan_id} already exists")
        self.plan_id = plan_id


class PlanNotFoundError(Exception):
    """Attempted an operation on a plan whose stream has no events."""

    def __init__(self, plan_id: UUID) -> None:
        super().__init__(f"Plan {plan_id} not found")
        self.plan_id = plan_id


class PracticeDeprecatedError(Exception):
    """Attempted to bind a Plan to a Deprecated Practice.

    Per gate-review Q5: Practice/Method deprecation is advisory at
    the inner layer (Practice itself doesn't reject operations when
    deprecated), but Plan binding rejects deprecated upstream
    recipes — you can't make a new binding against a tombstoned
    template. Mapped to HTTP 409 (state-conflict family).
    """

    def __init__(self, practice_id: UUID) -> None:
        super().__init__(f"Cannot bind Plan to Practice {practice_id}: Practice is Deprecated")
        self.practice_id = practice_id


class MethodDeprecatedError(Exception):
    """Attempted to bind a Plan whose Practice references a Deprecated Method.

    Mirrors `PracticeDeprecatedError` shape. Mapped to HTTP 409.
    """

    def __init__(self, method_id: UUID) -> None:
        super().__init__(f"Cannot bind Plan to Method {method_id}: Method is Deprecated")
        self.method_id = method_id


class AssetDecommissionedError(Exception):
    """Attempted to bind a Plan to one or more Decommissioned Assets.

    Plans are forward-looking bindings; binding to a decommissioned
    Asset is structurally inconsistent (the Asset cannot be
    re-activated from Decommissioned per the Asset FSM). Carries
    the list of offending asset_ids for diagnostics. Mapped to HTTP 409.
    """

    def __init__(self, asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot bind Plan: the following Assets are Decommissioned: "
            f"{[str(a) for a in asset_ids]}"
        )
        self.asset_ids = asset_ids


class PlanCannotVersionError(Exception):
    """Attempted to version a plan not in `Defined` or `Versioned`.

    Multi-source guard: `version_plan` accepts both `Defined` (first
    revision) and `Versioned` (subsequent revisions — operators bump
    v1 → v2 → v3 over time). Only `Deprecated` is rejected (you
    can't revise a deprecated plan).

    Per-transition error class — same naming convention as
    `MethodCannotVersionError` (Recipe 6b), `PracticeCannotVersionError`
    (Recipe 6d-2), `CapabilityCannotVersionError` (Equipment 5f-2).
    Mapped to HTTP 409.
    """

    def __init__(self, plan_id: UUID, current_status: "PlanStatus") -> None:
        super().__init__(
            f"Plan {plan_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{PlanStatus.DEFINED.value} or {PlanStatus.VERSIONED.value}"
        )
        self.plan_id = plan_id
        self.current_status = current_status


class PlanCannotDeprecateError(Exception):
    """Attempted to deprecate a plan not in `Defined` or `Versioned`.

    Multi-source guard. Re-deprecating an already-`Deprecated` plan
    raises (strict-not-idempotent). Mirrors
    `PracticeCannotDeprecateError` / `MethodCannotDeprecateError`
    shape. Mapped to HTTP 409.
    """

    def __init__(self, plan_id: UUID, current_status: "PlanStatus") -> None:
        super().__init__(
            f"Plan {plan_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{PlanStatus.DEFINED.value} or {PlanStatus.VERSIONED.value}"
        )
        self.plan_id = plan_id
        self.current_status = current_status


class InvalidPlanVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    InvalidPracticeVersionTagError / InvalidMethodVersionTagError /
    InvalidCapabilityVersionTagError. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Plan version tag must be 1-{PLAN_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class PlanCapabilitiesNotSatisfiedError(Exception):
    """The bound Assets' capabilities don't cover the Method's needs.

    Carries the missing capability ids — those required by the
    Method but not present in any bound Asset's `capabilities`.
    Mapped to HTTP 409 (state-conflict family; the binding is
    structurally invalid given current Asset state).

    Per gate-review Q3: check is on each bound Asset's OWN
    capabilities (no hierarchy traversal). Operators model
    Asset.capabilities at whatever granularity makes sense (Assembly
    level for composed devices, Device level for leaves) and bind
    the Assets that actually carry the needed capabilities.
    """

    def __init__(self, missing_capability_ids: frozenset[UUID]) -> None:
        super().__init__(
            f"Plan capabilities not satisfied: bound Assets are missing "
            f"capabilities {sorted(str(c) for c in missing_capability_ids)}"
        )
        self.missing_capability_ids = missing_capability_ids


@dataclass(frozen=True)
class PlanName:
    """Display name for a plan. Trimmed; 1-200 chars.

    Tenth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_name` helper hoisted in 6e-1 (see
    `cora.infrastructure.name`). The helper preserves per-VO
    distinctness (separate frozen dataclass type, separate error
    class) while removing the trim+length-check duplication that
    had accumulated across 10 aggregates.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=PLAN_NAME_MAX_LENGTH,
            error_class=InvalidPlanNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Plan:
    """Aggregate root: a Practice bound to specific Asset instances.

    `practice_id` is the Practice this Plan binds (eventual-
    consistency ref). `asset_ids` is the set of Assets this Plan
    binds (multi-asset; at least one required, validated at decide
    time). `status` defaults to `Defined`.

    `version` is the operator-supplied label of the most recent
    `version_plan` call (None until first version). State always
    holds the latest tag — past tags live in the event stream as
    `PlanVersioned` events. No `current_` prefix because state by
    definition holds current values (same convention as `status`,
    `name`). Free-text validated at API boundary + defensively in
    the decider; no VO. Default None keeps pre-6e-2 PlanDefined-
    only streams folding cleanly (additive-state pattern). Mirrors
    Method/Practice/Capability `version` semantics: preserved across
    deprecation as an audit signal of the last revision before
    deprecation.
    """

    id: UUID
    name: PlanName
    practice_id: UUID
    asset_ids: frozenset[UUID]
    status: PlanStatus = PlanStatus.DEFINED
    version: str | None = None
