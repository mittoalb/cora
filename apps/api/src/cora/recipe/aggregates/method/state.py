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
`CapabilityName`, `AssetName`. The 5a gate-review locked the
`BoundedName` factory extraction as deferred until first per-VO
divergence OR ~10 instances; this commit doesn't change that.

## Frozensets in state, lists in payloads

`needs_capabilities` is `frozenset[UUID]` in domain state
(deduplicated, hashable, set-membership in O(1) for Plan-binding
checks) and `list[UUID]` in event payloads (JSON-friendly, sorted
for determinism). Same precedent as Trust's Policy
`permitted_principals` / `permitted_commands`. The evolver bridges
the two. Sorting in `to_payload` keeps the persisted bytes
deterministic — same logical capability set, same payload, same
idempotency hash.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

METHOD_NAME_MAX_LENGTH = 200
METHOD_VERSION_TAG_MAX_LENGTH = 50


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

    Eighth occurrence of the trimmed-bounded-name VO pattern. The
    BoundedName factory extraction stays deferred per the 5a
    gate-review decision (revisit at first per-VO divergence or
    ~10 instances).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > METHOD_NAME_MAX_LENGTH:
            raise InvalidMethodNameError(self.value)
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
    """

    id: UUID
    name: MethodName
    needs_capabilities: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: MethodStatus = MethodStatus.DEFINED
    version: str | None = None
