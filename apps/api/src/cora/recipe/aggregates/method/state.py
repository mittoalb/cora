"""Method aggregate state, value objects, status enum, and domain errors.

`Method` is the abstract recipe — the technique class as published
by the vendor or scientific community. Examples: "X-ray Fluorescence
Mapping", "Step Tomography", "Ptychography". Equipment-agnostic
(refers to `Capability` ids only, not specific Asset instances).

Per the BC map's recipe ladder, Method ≈ ISA-88 General Recipe. The
facility's adapted version lives in `Practice` (6d), and the
concrete Asset binding lives in `Plan` (6e).

## Phase 6a scope

Minimal Method:
  - `id` + `name`
  - `needs_capabilities: frozenset[UUID]` — the Capability ids this
    Method requires. Composable: a "Fly Tomography" Method has
    needs_capabilities = {Tomography_id, FlyScan_id}. At Plan
    binding time (6e), the operator picks an Asset whose
    capabilities ⊇ method.needs_capabilities.
  - `status` (defaults `Defined`).

`Versioned` and `Deprecated` transitions land in 6b. Description /
owner / additional facets defer to 6c.

## needs_capabilities — eventual-consistency stance

The decider does NOT verify each Capability id refers to a real
Capability stream in the event store. Same precedent as Trust's
Conduit zone refs (3b) and Asset parent refs (5b). Typos produce
"dangling" Methods; downstream Plan binding (6e) is where the
mismatch will surface (Asset can't satisfy the requirement). For
day-one ergonomics this is fine; structural validation can be
layered on at the API boundary later if pilot demand emerges.

Empty `needs_capabilities` is allowed (a Method that needs no
specific equipment capability — rare but operationally valid for
purely procedural Methods like "Sample Cleaning").

## Status as enum-in-state, derived-from-event-type-in-evolver

`MethodStatus` is a `StrEnum` so the values would serialize
naturally as JSON-friendly strings IF carried in an event payload.
Today they aren't: state holds the enum (typed) and the evolver
derives the new status from the event TYPE — same precedent as
`CapabilityStatus`, `SubjectStatus`, `AssetLifecycle`.

## Eighth bounded-name VO

`MethodName` is the **eighth** trimmed-bounded-name VO after
`ActorName`, `ZoneName`, `ConduitName`, `PolicyName`, `SubjectName`,
`CapabilityName`, `AssetName`. Phase 6e-1 hoisted the shared
trim+length-check logic to `cora.infrastructure.bounded_text.validate_bounded_text`
once the 10th VO (PlanName) landed; MethodName now calls that helper
while keeping its own frozen dataclass type and per-aggregate error
class. See the helper module's docstring for the design rationale.

## Frozensets in state, lists in payloads

`needs_capabilities` is `frozenset[UUID]` in domain state
(deduplicated, hashable, set-membership in O(1) for Plan-binding
checks) and `list[UUID]` in event payloads (JSON-friendly, sorted
for determinism). Same precedent as Trust's Policy
`principals_permitted` / `commands_permitted`. The evolver bridges
the two. Sorting in `to_payload` keeps the persisted bytes
deterministic — same logical capability set, same payload, same
idempotency hash.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

METHOD_NAME_MAX_LENGTH = 200
METHOD_VERSION_TAG_MAX_LENGTH = 50
# Phase 10b: needs_supplies element bounds. Mirrors Supply.kind shape
# (cora.supply.aggregates.supply.state.SUPPLY_KIND_MAX_LENGTH = 50)
# so per-element validation in the Method decider stays consistent
# with what Supply itself accepts at register_supply time. See
# [[project_supply_design]] §"Phase 10b — Method.needs_supplies consumer"
# for the design lock.
METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH = 50


class MethodStatus(StrEnum):
    """The Method's lifecycle state.

    Transitions land per-slice in Phase 6b:
      - Defined -> Versioned        (version_method)
      - (Defined | Versioned) -> Deprecated   (deprecate_method)

    `Defined` is the genesis state set by `define_method`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidMethodNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method name must be 1-{METHOD_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class MethodAlreadyExistsError(Exception):
    """Attempted to define a method whose stream already has events."""

    def __init__(self, method_id: UUID) -> None:
        super().__init__(f"Method {method_id} already exists")
        self.method_id = method_id


class MethodNotFoundError(Exception):
    """Attempted an operation on a method whose stream has no events."""

    def __init__(self, method_id: UUID) -> None:
        super().__init__(f"Method {method_id} not found")
        self.method_id = method_id


class MethodCannotVersionError(Exception):
    """Attempted to version a method not in `Defined` or `Versioned`.

    Multi-source guard: `version_method` accepts both `Defined`
    (first revision) and `Versioned` (subsequent revisions —
    operators bump v1 → v2 → v3 over time as the recipe's
    parameters or step list are refined). Only `Deprecated` is
    rejected (you can't revise a deprecated method — un-deprecate
    first if you want to bring it back, though that slice doesn't
    exist today).

    Mirrors `CapabilityCannotVersionError` shape and semantics
    (Equipment 5f-2). Same deliberate divergence from strict-not-
    idempotent: re-versioning with the same tag succeeds and emits a
    fresh event (re-attestation is a legitimate audit moment).
    Pinned by tests/unit/recipe/test_version_method_decider.py.
    """

    def __init__(self, method_id: UUID, current_status: "MethodStatus") -> None:
        super().__init__(
            f"Method {method_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{MethodStatus.DEFINED.value} or {MethodStatus.VERSIONED.value}"
        )
        self.method_id = method_id
        self.current_status = current_status


class MethodCannotDeprecateError(Exception):
    """Attempted to deprecate a method not in `Defined` or `Versioned`.

    Multi-source guard: `deprecate_method` accepts both `Defined`
    (deprecating before any revisions) and `Versioned` (deprecating
    a revised recipe). Re-deprecating an already-`Deprecated` method
    raises (strict-not-idempotent). Mirrors
    `CapabilityCannotDeprecateError` shape.

    Existing Plans / Practices that reference this Method are NOT
    automatically invalidated. Deprecation is advisory at the BC
    layer; future Plan-side enrichment may surface a warning at
    bind-time when referencing a deprecated Method.
    """

    def __init__(self, method_id: UUID, current_status: "MethodStatus") -> None:
        super().__init__(
            f"Method {method_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{MethodStatus.DEFINED.value} or {MethodStatus.VERSIONED.value}"
        )
        self.method_id = method_id
        self.current_status = current_status


class InvalidMethodNeedsSuppliesError(ValueError):
    """One of the supplied needs_supplies kind strings is empty,
    whitespace-only, or too long.

    Phase 10b. Validated at the API boundary via Pydantic per-element
    `min_length=1, max_length=50`, AND defensively at the decider via
    this error so direct in-process callers (sagas, tests) get the
    same protection. The diagnostic carries the offending element.

    Per-element bound mirrors `InvalidSupplyKindError` from the Supply
    BC (the kind is the abstract label; Method's needs_supplies
    references kind values that Supply registrations carry). See
    [[project_supply_design]] §"Phase 10b — Method.needs_supplies
    consumer" for the design lock + asymmetry rationale (frozenset[str]
    on Method vs frozenset[UUID] for needs_capabilities: Supply is
    INSTANCE-aggregate per facility, sharing a `kind` label;
    Capability is TYPE-aggregate, one global definition referenced
    by UUID).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method needs_supplies kind must be 1-{METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidMethodVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    `InvalidCapabilityVersionTagError` (Equipment 5f-2) and
    `InvalidMethodNameError`.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Method version tag must be 1-{METHOD_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class MethodName:
    """Display name for a method. Trimmed; 1-200 chars.

    Eighth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper hoisted in 6e-1 (see
    `cora.infrastructure.bounded_text`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=METHOD_NAME_MAX_LENGTH,
            error_class=InvalidMethodNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Method:
    """Aggregate root: an abstract technique-class recipe.

    `needs_capabilities` is a frozenset of Capability ids the Method
    requires. Eventual-consistency stance: existence is not verified
    at decide time; mismatch surfaces at Plan binding (6e).

    `version` is the operator-supplied label of the most recent
    `version_method` call (None until first version). State always
    holds the latest tag — past tags live in the event stream as
    `MethodVersioned` events. No `current_` prefix because state by
    definition holds current values (same convention as `status`,
    `name`). Free-text validated at API boundary + defensively in the
    decider; no VO. Default None keeps pre-6b MethodDefined-only
    streams folding cleanly (additive-state pattern). Mirrors
    Capability's `version` semantics (Equipment 5f-2): preserved
    across deprecation as an audit signal of the last revision before
    deprecation.

    `parameters_schema` is the optional JSON Schema (Draft 2020-12,
    constrained subset) declaring the shape of parameter dicts that
    Plans (6g-b) and Runs (6g-c) carry for this Method. Defaults to
    None for legacy Methods (additive-state pattern); None means
    "this Method declares no parameter contract — accept any dict".
    Distinct from `{}` (empty schema, "operator explicitly said no
    parameters"). Subset shared with Capability.settings_schema via
    `cora.infrastructure.json_schema_subset`. See
    [[project_run_parameters_design]] for the full 6g family layout.
    """

    id: UUID
    name: MethodName
    needs_capabilities: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: MethodStatus = MethodStatus.DEFINED
    version: str | None = None
    parameters_schema: dict[str, Any] | None = field(default=None)
    # Phase 10b: needs_supplies references Supply.kind STRINGS (not
    # UUIDs). Asymmetric with needs_capabilities (frozenset[UUID]) by
    # design: Capability is a TYPE registry (one global definition,
    # referenced by UUID); Supply is an INSTANCE aggregate (multiple
    # per facility, each with its own availability state, sharing a
    # `kind` label). Methods are facility-portable so they reference
    # the abstract kind, not a per-facility instance UUID. Defaults
    # to empty frozenset (additive-state pattern; pre-10b
    # MethodDefined-only streams fold cleanly via payload.get default).
    # See [[project_supply_design]] §"Phase 10b — Method.needs_supplies
    # consumer" for the full design lock.
    needs_supplies: frozenset[str] = field(default_factory=frozenset[str])
