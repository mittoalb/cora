"""Asset aggregate state, value objects, status enums, and domain errors.

`Asset` is the physical equipment instance: a beamline, a detector,
a sample changer, an HPC node. Hierarchical via `parent_id` (forms
a tree, NOT a DAG — single-parent rule per BC map). Carries a
`level` discriminator (Enterprise / Site / Area / Unit / Assembly /
Device, ISA-88-derived), a `lifecycle` FSM
(Commissioned -> Active -> Maintenance -> Decommissioned), a
`condition` enum (Nominal / Degraded / Faulted, 5g-b: orthogonal to
lifecycle), a `settings` dict (5g-c: slow-changing operational
parameters validated at write time against the union of assigned
Capabilities' settings_schemas), and `ports` (5h: typed connection
points for trigger / encoder / sync / network signals; declarations
of what ports the equipment HAS — Plan.wiring (6h) carries the
actual port-to-port connections).

## Phase 5b scope

Minimal Asset: `id` + `name` + `level` + `lifecycle` (defaults
`Commissioned`) + `parent_id: UUID | None`. Lifecycle transitions
land in 5c (activate, decommission), 5e (maintenance cycle).
Hierarchy mutation (`AssetRelocated`) lands in 5d. Additive
facets — `condition`, `settings`, `ports`, `owner`,
`persistent_id` (PIDINST DOI) — defer to 5f+.

## Hierarchy rule (5b decider)

Per the BC map:
  - `Enterprise` is the root level — `parent_id` MUST be null.
  - All other levels (Site / Area / Unit / Assembly / Device) MUST
    have a `parent_id`.

Eventual-consistency stance for the parent ref: the decider does
NOT verify the referenced parent Asset exists in the event store.
Same precedent as Trust's Conduit zone refs (3b-pinned). Cycle
detection (target's ancestors must not include this asset) requires
walking the parent chain via additional event-store queries; defer
to projection-worker era. Single-parent tree is enforced
structurally (one `parent_id` field, can't be a list).

**Levels are conventional, not enforced** per the BC map: the
decider does NOT check that a Device's parent is an Assembly.
`Device`-in-`Device` is allowed when reality demands it (smart
instruments with addressable sub-modules).

## Status as enum-in-state, derived-from-event-type-in-evolver

`AssetLifecycle` is a `StrEnum` so values serialize naturally as
JSON-friendly strings IF carried in an event payload. State holds
the enum (typed); evolver derives lifecycle from event type
(`AssetRegistered → COMMISSIONED`, future `AssetActivated → ACTIVE`).
Same precedent as `SubjectStatus` / `CapabilityStatus`.

`AssetLevel` is also a StrEnum but its value DOES travel in event
payloads (level is set at registration and doesn't change — there
are no AssetLevelChanged events). The payload carries the string;
the evolver reconstructs via `AssetLevel(payload["level"])`.

## Seventh bounded-name VO

`AssetName` is the **seventh** trimmed-bounded-name VO. Phase 6e-1
hoisted the shared trim+length-check logic to
`cora.infrastructure.name.validate_name` once the 10th VO (PlanName)
landed; AssetName now calls that helper while keeping its own frozen
dataclass type and per-aggregate error class.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.infrastructure.name import validate_name

ASSET_NAME_MAX_LENGTH = 200


class AssetLevel(StrEnum):
    """The hierarchical level of an Asset.

    Per the BC map (ISA-88-derived, single-word convention):
      - `Enterprise` — root; the institution itself
      - `Site` — a facility (e.g., APS)
      - `Area` — a section of a site (e.g., the experimental hall)
      - `Unit` — an operational unit (e.g., a beamline)
      - `Assembly` — a composed component (ISA-88 "Equipment Module")
      - `Device` — an addressable control surface (ISA-88 "Control Module")

    Common pattern is the strict ordering above, but Device-in-Device
    is allowed when reality demands it (smart instruments). Levels
    are conventional, not enforced — the decider does not check that
    a Device's parent is an Assembly.
    """

    ENTERPRISE = "Enterprise"
    SITE = "Site"
    AREA = "Area"
    UNIT = "Unit"
    ASSEMBLY = "Assembly"
    DEVICE = "Device"


class AssetLifecycle(StrEnum):
    """The Asset's lifecycle state.

    Transitions land per-slice:
      - 5c: Commissioned -> Active        (activate_asset)
      - 5c: (Commissioned | Active) -> Decommissioned   (decommission_asset)
      - 5e: Active -> Maintenance         (enter_maintenance)
      - 5e: Maintenance -> Active         (restore_from_maintenance)
      - 5e (extends 5c): decommission accepts Maintenance as third source

    `Commissioned` is the genesis state set by `register_asset`. The
    enum values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    COMMISSIONED = "Commissioned"
    ACTIVE = "Active"
    MAINTENANCE = "Maintenance"
    DECOMMISSIONED = "Decommissioned"


class PortDirection(StrEnum):
    """The direction of an Asset port (5h).

    Two values only: `INPUT` (receives a signal) and `OUTPUT`
    (drives a signal). Bidirectional devices declare TWO ports with
    opposite directions; matches PandABox / EPICS convention. A
    single `BIDIRECTIONAL` value would create ambiguity at wire-up
    time (Plan.wiring needs to know which side is the source).
    """

    INPUT = "Input"
    OUTPUT = "Output"


PORT_NAME_MAX_LENGTH = 100
PORT_SIGNAL_TYPE_MAX_LENGTH = 50


class InvalidAssetPortNameError(ValueError):
    """The supplied port name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset port name must be 1-{PORT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAssetPortSignalTypeError(ValueError):
    """The supplied port signal_type is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset port signal_type must be 1-{PORT_SIGNAL_TYPE_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class AssetPort:
    """A typed connection point exposed by an Asset (5h).

    Tuple `(name, direction, signal_type)` describes one port. The
    Asset declares what ports it HAS via `add_asset_port` /
    `remove_asset_port`; the connection between two ports (which
    port wires to which) lives in `Plan.wiring` (6h), not here.

    `name` is operator-supplied within the Asset's scope (e.g.
    `"trigger_in"`, `"encoder_a"`, `"sync_clock"`). Trimmed and
    bounded 1-100 chars. Asset-wide name uniqueness is enforced by
    the `add_asset_port` decider, NOT by this dataclass.

    `signal_type` is operator-supplied free text 1-50 chars
    (`"TTL"`, `"LVDS"`, `"Encoder"`, `"Network"`, `"Sync"`, etc.).
    Free-form intentionally; promote to a closed StrEnum once the
    pilot vocabulary settles (see project_asset_ports_design memo).
    """

    name: str
    direction: PortDirection
    signal_type: str

    def __post_init__(self) -> None:
        trimmed_name = self.name.strip()
        if not trimmed_name or len(trimmed_name) > PORT_NAME_MAX_LENGTH:
            raise InvalidAssetPortNameError(self.name)
        trimmed_signal = self.signal_type.strip()
        if not trimmed_signal or len(trimmed_signal) > PORT_SIGNAL_TYPE_MAX_LENGTH:
            raise InvalidAssetPortSignalTypeError(self.signal_type)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install trimmed values.
        object.__setattr__(self, "name", trimmed_name)
        object.__setattr__(self, "signal_type", trimmed_signal)


class AssetCondition(StrEnum):
    """The Asset's real-time device-health state.

    Orthogonal to lifecycle: lifecycle answers "is this device part
    of inventory and assignable", condition answers "is it actually
    working right now". An Active asset can be Faulted (broken but
    still owned); a Decommissioned asset can be discovered Faulted on
    inventory check (honest about device-state-in-storage).

    Transitions land per-slice (5g-b), each moves to a fixed target
    from any source:
      - degrade_asset            -> Degraded
      - fault_asset              -> Faulted
      - restore_asset            -> Nominal

    `Nominal` is the default at registration time (no synthetic
    initialization event; default-via-state). Pattern matches PI-System
    asset-health attributes (Good / Warning / Bad) and SEMI E10's
    productive vs unproductive time orthogonality.
    """

    NOMINAL = "Nominal"
    DEGRADED = "Degraded"
    FAULTED = "Faulted"


class InvalidAssetNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset name must be 1-{ASSET_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAssetSettingsError(ValueError):
    """The proposed Asset.settings dict failed cross-Capability validation.

    Three failure modes (5g-c):
      1. A key in the proposed settings is not declared by any
         currently-assigned Capability's settings_schema (orphan key
         on a fully-schema-covered Asset).
      2. A value violates the schema constraints declared for its
         key by one or more assigned Capabilities (intersection via
         `allOf` semantics; the most restrictive wins).
      3. Two or more assigned Capabilities declare the same key with
         incompatible types (true conflict; no value satisfies both).

    Mapped to HTTP 400 by the equipment BC's exception handler. The
    `reason` string identifies the offending key(s) and, where
    applicable, the conflicting Capability ids.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Asset settings: {reason}")
        self.reason = reason


class InvalidAssetParentError(ValueError):
    """The hierarchy rule was violated.

    Two failure modes:
      - Enterprise-level Asset supplied a non-null `parent_id`
        (Enterprise is the root; cannot have a parent)
      - Non-Enterprise-level Asset supplied a null `parent_id`
        (Site / Area / Unit / Assembly / Device must have a parent)

    Eventual-consistency stance: this decider rule does NOT check
    that the referenced parent Asset exists. Cycle detection
    (target's ancestors must not include this asset) is a separate
    deferred concern (requires walking the parent chain via the
    event store; revisit when projection-worker exists).
    """


class AssetAlreadyExistsError(Exception):
    """Attempted to register an asset whose stream already has events."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Asset {asset_id} already exists")
        self.asset_id = asset_id


class AssetNotFoundError(Exception):
    """Attempted an operation on an asset whose stream has no events."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Asset {asset_id} not found")
        self.asset_id = asset_id


class AssetCannotActivateError(Exception):
    """Attempted to activate an asset not in the `Commissioned` lifecycle.

    Strict semantics: re-activating an already-`Active` asset also
    raises (rather than no-op or always-emit). Per-transition error
    class — same naming convention as `SubjectCannot<X>Error`. The
    current lifecycle is carried as `current_lifecycle` for
    diagnostics; the error message lists both the current and the
    expected source state.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot be activated: currently in lifecycle "
            f"{current_lifecycle.value}, activate requires "
            f"{AssetLifecycle.COMMISSIONED.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotDecommissionError(Exception):
    """Attempted to decommission an asset not in `Commissioned`, `Active`, or `Maintenance`.

    Multi-source guard: `decommission` accepts `Commissioned` (asset
    never went into service — operator changed mind), `Active` (asset
    retired from service), and `Maintenance` (asset retired during a
    maintenance window). The decider's `_DECOMMISSIONABLE_LIFECYCLES`
    tuple is the single edit point that controls the allowed source
    set; the error message lists currently-allowed source states for
    diagnostic clarity. Mirrors Subject's `SubjectCannotRemoveError`
    pattern.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot be decommissioned: currently in lifecycle "
            f"{current_lifecycle.value}, decommission requires "
            f"{AssetLifecycle.COMMISSIONED.value}, {AssetLifecycle.ACTIVE.value}, "
            f"or {AssetLifecycle.MAINTENANCE.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotEnterMaintenanceError(Exception):
    """Attempted to enter maintenance on an asset not in `Active`.

    Strict semantics: re-entering maintenance on an already-`Maintenance`
    asset also raises (rather than no-op). Industrial convention: only
    in-service (Active) assets enter maintenance; Commissioned assets
    are still pre-service, Decommissioned ones are retired. Per-transition
    error class — same naming convention as `SubjectCannot<X>Error` and
    `AssetCannotActivateError`.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot enter maintenance: currently in lifecycle "
            f"{current_lifecycle.value}, enter_maintenance requires "
            f"{AssetLifecycle.ACTIVE.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotRestoreFromMaintenanceError(Exception):
    """Attempted to restore-from-maintenance on an asset not in `Maintenance`.

    Strict semantics: restoring an already-`Active` asset also raises
    (the maintenance window has already ended). Mirrors
    AssetCannotEnterMaintenanceError. Single-source guard like activate.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: "AssetLifecycle") -> None:
        super().__init__(
            f"Asset {asset_id} cannot be restored from maintenance: currently in lifecycle "
            f"{current_lifecycle.value}, restore_from_maintenance requires "
            f"{AssetLifecycle.MAINTENANCE.value}"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetCannotAddCapabilityError(Exception):
    """Attempted to add a Capability to an asset under disqualifying conditions.

    Capability mutation (5f-1): like relocate, has multiple
    disqualifying conditions that don't share a single state-mismatch
    shape. They collapse into one error class with a diagnostic
    `reason` string that surfaces in the route's 409 body:

      - asset is `Decommissioned` (retired; no further capability changes)
      - capability already in `asset.capabilities` (strict-not-idempotent;
        same precedent as activate / mount-second-call-raises)

    Eventual-consistency: the decider does NOT verify the referenced
    Capability id refers to a real Capability stream. Same precedent
    as Trust Conduit zone refs (3b) and Method.needs_capabilities
    (6a).
    """

    def __init__(self, asset_id: UUID, capability_id: UUID, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot add capability {capability_id}: {reason}")
        self.asset_id = asset_id
        self.capability_id = capability_id
        self.reason = reason


class AssetCannotRemoveCapabilityError(Exception):
    """Attempted to remove a Capability from an asset under disqualifying conditions.

    Mirrors `AssetCannotAddCapabilityError`. Disqualifying conditions:

      - asset is `Decommissioned` (retired)
      - capability not in `asset.capabilities` (strict-not-idempotent)
    """

    def __init__(self, asset_id: UUID, capability_id: UUID, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot remove capability {capability_id}: {reason}")
        self.asset_id = asset_id
        self.capability_id = capability_id
        self.reason = reason


class AssetCannotAddPortError(Exception):
    """Attempted to add a port to an Asset under disqualifying conditions (5h).

    Two failure modes:
      - asset is `Decommissioned` (retired; no further port changes)
      - port name is already in `asset.ports` (strict-not-idempotent;
        same convention as Capability mutation)

    Mirrors `AssetCannotAddCapabilityError`. The `port_name` is
    surfaced as a separate field for diagnostics; the `reason`
    string is what the route's 409 body shows.
    """

    def __init__(self, asset_id: UUID, port_name: str, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot add port {port_name!r}: {reason}")
        self.asset_id = asset_id
        self.port_name = port_name
        self.reason = reason


class AssetCannotRemovePortError(Exception):
    """Attempted to remove a port from an Asset under disqualifying conditions (5h).

    Two failure modes:
      - asset is `Decommissioned` (retired)
      - no port with the given name in `asset.ports` (strict-not-
        idempotent; symmetric with `AssetCannotAddPortError`)
    """

    def __init__(self, asset_id: UUID, port_name: str, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot remove port {port_name!r}: {reason}")
        self.asset_id = asset_id
        self.port_name = port_name
        self.reason = reason


class AssetCannotRelocateError(Exception):
    """Attempted to relocate an asset under disqualifying conditions.

    Hierarchy mutation (5d): unlike the lifecycle-transition errors
    (Activate/Decommission), relocation has multiple disqualifying
    conditions that don't share a single state-mismatch shape. They
    all collapse into one error class with a diagnostic `reason`
    string that surfaces in the route's 409 body:

      - asset is `Enterprise` level (root; cannot have a parent at all)
      - asset is `Decommissioned` (retired; no further hierarchy changes)
      - target_parent_id == asset_id (single-parent-tree self-loop)
      - target_parent_id == current parent_id (no-op)

    Cycle detection beyond the trivial self-loop case (target's
    ancestor chain contains the asset) is **deferred** — requires
    walking the parent chain via additional event-store queries;
    revisit when projection-worker exists. Documented as a known
    gap.
    """

    def __init__(self, asset_id: UUID, reason: str) -> None:
        super().__init__(f"Asset {asset_id} cannot be relocated: {reason}")
        self.asset_id = asset_id
        self.reason = reason


@dataclass(frozen=True)
class AssetName:
    """Display name for an asset. Trimmed; 1-200 chars.

    Seventh occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_name` helper hoisted in 6e-1 (see
    `cora.infrastructure.name`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=ASSET_NAME_MAX_LENGTH,
            error_class=InvalidAssetNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Asset:
    """Aggregate root: a physical equipment instance.

    `parent_id` is the immediate parent in the hierarchy tree.
    `None` only when `level == Enterprise` (root). Mutable across
    `AssetRelocated` events (5d).

    `capabilities` is the set of Capability ids this asset can
    perform. Operationally curated: operators add via
    `add_asset_capability` when commissioning a new technique on the
    asset, remove via `remove_asset_capability` when retiring one.
    Used at Plan binding time (6e) for the structural check
    `asset.capabilities ⊇ method.needs_capabilities`. Eventual-
    consistency: each Capability id is NOT verified against the
    Capability stream at decide time. Defaults to empty so prior
    `AssetRegistered`-only streams fold cleanly without an upcaster
    (the additive-state pattern; see CONTRIBUTING.md).

    `condition` (5g-b): real-time device health, orthogonal to
    lifecycle. Defaults to `AssetCondition.NOMINAL` at registration
    (no synthetic initialization event); transitions land via the
    degrade / fault / restore slices. Older AssetRegistered-only
    streams from before 5g-b fold cleanly with the default
    (additive-state pattern).

    `settings` (5g-c): slow-changing operational parameters
    (gap_mm, energy_kev, exposure_ms, filter_material, etc.).
    Validated at write time against the union of currently-assigned
    Capabilities' `settings_schema` declarations (5g-a). Updated via
    the `update_asset_settings` slice with PATCH RFC 7396 merge
    semantics. Defaults to empty dict; pre-5g-c streams fold cleanly
    via the additive-state pattern.

    `ports` (5h): typed connection points the Asset exposes
    (trigger_in, encoder_a, sync_clock, etc.). Each AssetPort is a
    name + direction + signal_type tuple. Updated incrementally via
    `add_asset_port` / `remove_asset_port` slices (mirrors the
    Capability-mutation precedent). Defaults to empty frozenset;
    pre-5h streams fold cleanly via the additive-state pattern.
    Plan.wiring (6h) will reference these by name to declare port-
    to-port connections.

    Future additive facets: `owner`, `persistent_id`. The state-
    level fields land with defaults for the same forward-
    compatibility reason.
    """

    id: UUID
    name: AssetName
    level: AssetLevel
    parent_id: UUID | None
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED
    condition: AssetCondition = AssetCondition.NOMINAL
    # frozenset[UUID] generic-callable trick (PEP 585): plain
    # `frozenset` as default_factory triggers reportUnknownVariableType
    # under pyright strict because the empty frozenset has no element
    # type to infer. The parametrized form gives pyright the type
    # without runtime cost. Same trick used in Method.needs_capabilities.
    capabilities: frozenset[UUID] = field(default_factory=frozenset[UUID])
    # dict[str, Any] for runtime-typed operator-supplied settings.
    # Same default_factory pattern as capabilities — the empty dict
    # has no element types for pyright to infer, so the parametrized
    # `dict[str, Any]` callable is supplied as the factory.
    settings: dict[str, Any] = field(default_factory=dict[str, Any])
    # frozenset[AssetPort] for typed connection points (5h).
    # Same parametrized-callable trick as capabilities.
    ports: frozenset[AssetPort] = field(default_factory=frozenset[AssetPort])
