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
Method's needed_capabilities and each bound Asset's capabilities)
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
  - `union(asset.capabilities) ⊇ method.needed_capabilities` →
    `PlanCapabilitiesNotSatisfiedError`

Handler-side load misses become `PracticeNotFoundError` /
`MethodNotFoundError` / `AssetNotFoundError` (defined on the
respective aggregates) before reaching the decider. The four
errors above are Plan-domain errors specific to "you tried to bind
to something whose state forbids binding"; they live in this
module.

This is the first decider in the codebase that takes cross-
aggregate state as input. The pattern is documented in
CONTRIBUTING.md as the canonical approach for cross-validating
deciders. Second instance shipped in `start_run` (Phase 6f-1) with
`RunStartContext` of the same shape.

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
helper got hoisted to `cora.infrastructure.bounded_text.validate_bounded_text`
(see that module's docstring). PlanName uses the helper from day
one; the prior 9 VOs were refactored in the same 6e-1 commit.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

PLAN_NAME_MAX_LENGTH = 200
PLAN_VERSION_TAG_MAX_LENGTH = 50
WIRE_PORT_NAME_MAX_LENGTH = 100  # mirrors PORT_NAME_MAX_LENGTH on AssetPort (5h)


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


class InvalidPlanDefaultParametersError(ValueError):
    """The supplied Plan default_parameters dict failed validation
    against the owning Method's parameters_schema (Phase 6g-b).

    Strict when Method.parameters_schema is None: non-empty defaults
    are rejected (Method declares no contract; operators wanting
    parameter-less Methods declare `parameters_schema={}` explicitly).
    When the schema IS declared, the merged defaults must conform per
    jsonschema-rs Draft 2020-12. Mapped to HTTP 400 by the recipe BC's
    exception handler. Mirrors the 5g-c "no Capabilities + non-empty
    settings → reject" cross-BC anchor; see
    [[project_schema_validated_values_pattern]].
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Plan default_parameters: {reason}")
        self.reason = reason


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
    the shared `validate_bounded_text` helper hoisted in 6e-1 (see
    `cora.infrastructure.bounded_text`). The helper preserves per-VO
    distinctness (separate frozen dataclass type, separate error
    class) while removing the trim+length-check duplication that
    had accumulated across 10 aggregates.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
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

    `method_id` is the Method ultimately implemented by this Plan
    (originally captured in PlanDefined.method_id payload as audit-
    only data; promoted to state in 6g-b because the
    `update_plan_default_parameters` decider needs it to look up
    `Method.parameters_schema` for validation). Pre-6g-b PlanDefined
    streams fold cleanly: the evolver reads `method_id` from the
    payload field that was present from day one. Default-defaults to
    a sentinel via the constructor; in practice every well-formed
    stream sets it explicitly via PlanDefined. Mirrors the
    "state holds what future deciders need" precedent in the
    docstring above.

    `default_parameters: dict[str, Any]` (Phase 6g-b) is the
    operator-set defaults for parameters that downstream Runs
    (6g-c) merge with their per-run overrides. Validated against
    the owning Method's `parameters_schema` at decide time
    (STRICT when Method declares no schema: non-empty defaults
    rejected; operators wanting "no parameters" Methods declare
    `parameters_schema={}` explicitly. Mirrors 5g-c's
    "no Capabilities + non-empty settings → reject" anchor; see
    [[project_run_parameters_design]] §audit-correction).
    Defaults to empty dict for legacy Plans (additive-state pattern).
    The full dict is persisted; PATCH semantics handled by the slice
    via RFC 7396 `merge_patch`. Mirrors `Asset.settings` shape from 5g-c.

    `wires: frozenset[Wire]` (Phase 6h) is the typed graph of port-
    to-port connections between bound Assets. Each `Wire` carries
    a 4-tuple identifying source/target ports across two Assets.
    Mutated via `add_plan_wire` / `remove_plan_wire` slices (mirrors
    5h's add/remove_asset_port pattern). Direction is enforced
    (source=OUTPUT, target=INPUT), `signal_type` must match exactly,
    fan-out allowed (one source port → many target ports), fan-in
    forbidden (one target port = at most one incoming Wire). See
    [[project_plan_wiring_design]] for the locked design memo.
    Defaults to empty frozenset for legacy Plans (additive-state
    pattern).
    """

    id: UUID
    name: PlanName
    practice_id: UUID
    asset_ids: frozenset[UUID]
    status: PlanStatus = PlanStatus.DEFINED
    version: str | None = None
    method_id: UUID | None = None
    default_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    wires: frozenset["Wire"] = field(default_factory=frozenset["Wire"])


class InvalidWireError(ValueError):
    """A Wire's source / target port name is empty, whitespace-only,
    or exceeds the configured max length after trimming.

    Mirrors `InvalidAssetPortNameError` (5h). Mapped to HTTP 400 by
    the recipe BC's exception handler. Validation runs in the Wire
    VO's `__post_init__` so the route's Pydantic body keeps these
    to 422 by catching them at the boundary; deciders raise this
    when they construct a Wire from operator-supplied components.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Wire port name must be 1-{WIRE_PORT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class Wire:
    """A typed port-to-port connection between two bound Assets (Phase 6h).

    Tuple `(source_asset_id, source_port_name, target_asset_id,
    target_port_name)` describes one connection. The 4-tuple IS the
    identity; `frozenset[Wire]` deduplicates on the tuple.

    `source` / `target` labels match OPC UA SourceNode/TargetNode
    + Argo Workflows dependency direction (clearer than `from`/`to`,
    avoids collision with `PortDirection.{INPUT, OUTPUT}` that the
    `out`/`in` labels would create).

    Validation rules enforced at the decider level (NOT here):
      - source port must have `direction=OUTPUT`
      - target port must have `direction=INPUT`
      - `source_port.signal_type == target_port.signal_type` (exact match)
      - both endpoint asset_ids must be in the Plan's `asset_ids` set
      - both endpoint port_names must exist on their respective Asset.ports
      - target port can be the destination of at most one Wire (fan-in
        forbidden); fan-out (one source → many targets) is allowed
      - self-loops allowed iff `source_port_name != target_port_name`

    `__post_init__` validates only structural shape (port-name lengths
    + canonicalization via trim); the cross-aggregate validations
    above need a `PlanWireContext` and live in the slice deciders.

    See [[project_plan_wiring_design]] for the locked design memo.
    """

    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str

    def __post_init__(self) -> None:
        trimmed_source = self.source_port_name.strip()
        if not trimmed_source or len(trimmed_source) > WIRE_PORT_NAME_MAX_LENGTH:
            raise InvalidWireError(self.source_port_name)
        trimmed_target = self.target_port_name.strip()
        if not trimmed_target or len(trimmed_target) > WIRE_PORT_NAME_MAX_LENGTH:
            raise InvalidWireError(self.target_port_name)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install canonicalized names.
        object.__setattr__(self, "source_port_name", trimmed_source)
        object.__setattr__(self, "target_port_name", trimmed_target)


class PlanWireAlreadyExistsError(Exception):
    """Attempted to add a Wire that's already in the Plan's wire set.

    Strict-not-idempotent (mirrors 5h `add_asset_port`). Mapped to
    HTTP 409. Operators get clear feedback rather than a silent
    no-op so re-running a partially-applied template surface the
    duplicate.
    """

    def __init__(self, wire: Wire) -> None:
        super().__init__(
            f"Wire {_wire_diagnostic(wire)} is already in this Plan's wire set "
            "(strict-not-idempotent; remove the existing wire first if you mean "
            "to replace it)"
        )
        self.wire = wire


class PlanWireNotFoundError(Exception):
    """Attempted to remove a Wire that's not in the Plan's wire set.

    Strict-not-idempotent (symmetric with `PlanWireAlreadyExistsError`).
    Mapped to HTTP 404 (the target resource — this specific Wire — is
    not in the collection).
    """

    def __init__(self, wire: Wire) -> None:
        super().__init__(
            f"Wire {_wire_diagnostic(wire)} is not in this Plan's wire set "
            "(strict-not-idempotent; cannot remove a wire that does not exist)"
        )
        self.wire = wire


class PlanWireTargetAlreadyConnectedError(Exception):
    """The target port is already wired (fan-in is forbidden).

    Each `(target_asset_id, target_port_name)` pair can be the
    destination of at most one Wire (consensus across IEC 61131-3,
    IEC 61499 data arcs, PandABox mux, areaDetector NDArrayPort).
    Carries the existing Wire so operators can see what blocks the
    new add. Mapped to HTTP 409.

    Policy not physics: when fan-in is genuinely needed, introduce
    a `Combiner` Capability Asset with N inputs + 1 output and wire
    through it. See [[project_plan_wiring_design]].
    """

    def __init__(self, attempted: Wire, existing: Wire) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(attempted)}: target port is "
            f"already wired by {_wire_diagnostic(existing)} (fan-in forbidden)"
        )
        self.attempted = attempted
        self.existing = existing


class PlanWireAssetNotBoundError(Exception):
    """A Wire references an Asset that's not in the Plan's `asset_ids` set.

    Both endpoints of every Wire MUST reference Assets bound by the
    Plan. Carries the offending asset_ids for diagnostics. Mapped
    to HTTP 409 (state-conflict family; the wire is structurally
    invalid given current Plan binding).
    """

    def __init__(self, wire: Wire, missing_asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: the following endpoint "
            f"Assets are not bound by this Plan: "
            f"{[str(a) for a in missing_asset_ids]} (bind the Asset first via "
            "Plan re-definition, OR pick an Asset already bound)"
        )
        self.wire = wire
        self.missing_asset_ids = missing_asset_ids


class PlanWirePortNotFoundError(Exception):
    """A Wire references a port name that doesn't exist on its endpoint Asset.

    Strict forward-reference: Plan.wires rejects if either endpoint
    port doesn't currently exist on the bound Asset. Operators must
    add the port to the Asset (5h `add_asset_port`) BEFORE wiring
    against it. The same dependency-aware ordering applies to
    removal: remove the wire BEFORE removing the port (PostgreSQL FK
    shape; see [[project_plan_wiring_design]] §hot-swap procedure).

    Carries the offending port references as `(asset_id, port_name,
    direction_role)` triples where `direction_role` is "source" or
    "target". Mapped to HTTP 409.
    """

    def __init__(self, wire: Wire, missing: list[tuple[UUID, str, str]]) -> None:
        details = ", ".join(
            f"{role}={asset_id}:{port_name!r}" for asset_id, port_name, role in missing
        )
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: the following port "
            f"references don't exist on their endpoint Assets: {details} "
            "(add the port to the Asset first via add_asset_port, OR pick "
            "a port already declared)"
        )
        self.wire = wire
        self.missing = missing


class PlanWireDirectionMismatchError(Exception):
    """A Wire's source port is not OUTPUT, or its target port is not INPUT.

    Direction is enforced (universal across IEC 61131-3, IEC 61499,
    SysML, PandABox, EPICS, NiFi, LabVIEW). Carries the actual
    directions seen for diagnostics. Mapped to HTTP 409.
    """

    def __init__(
        self,
        wire: Wire,
        actual_source_direction: str,
        actual_target_direction: str,
    ) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: source must be "
            f"OUTPUT (got {actual_source_direction!r}), target must be "
            f"INPUT (got {actual_target_direction!r})"
        )
        self.wire = wire
        self.actual_source_direction = actual_source_direction
        self.actual_target_direction = actual_target_direction


class PlanWireSignalTypeMismatchError(Exception):
    """A Wire's source and target ports have different `signal_type` values.

    Exact-match required (matches IEC 61131-3 wire-type rules and
    LabVIEW G's broken-wire-on-mismatch). Carries both signal_types
    for diagnostics. Mapped to HTTP 409. If conversion is needed,
    add an explicit "converter" Asset; do not bake coercion into
    wire validation.
    """

    def __init__(
        self,
        wire: Wire,
        source_signal_type: str,
        target_signal_type: str,
    ) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: source signal_type "
            f"{source_signal_type!r} does not match target signal_type "
            f"{target_signal_type!r} (exact match required)"
        )
        self.wire = wire
        self.source_signal_type = source_signal_type
        self.target_signal_type = target_signal_type


class PlanWireSelfLoopError(Exception):
    """A Wire connects a port to itself (same asset_id AND same port_name).

    Self-loops between DIFFERENT ports on the same Asset are allowed
    (PandABox LUT block self-feedback pattern). Self-loops where
    source and target ports are identical are rejected as a
    degenerate case.
    """

    def __init__(self, wire: Wire) -> None:
        super().__init__(
            f"Cannot add wire {_wire_diagnostic(wire)}: source and target "
            "are the same port (self-loops on a single port are degenerate; "
            "use two distinct ports on the same Asset for legitimate "
            "feedback patterns)"
        )
        self.wire = wire


def _wire_diagnostic(wire: Wire) -> str:
    """Compact human-readable Wire renderer for error messages."""
    return (
        f"({wire.source_asset_id}:{wire.source_port_name!r} → "
        f"{wire.target_asset_id}:{wire.target_port_name!r})"
    )
