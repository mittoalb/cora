"""Asset aggregate state, value objects, status enums, and domain errors.

`Asset` is the physical equipment instance: a beamline, a detector,
a sample changer, an HPC node. Hierarchical via `parent_id` (forms
a tree, NOT a DAG — single-parent rule per BC map). Carries a
`level` discriminator (Enterprise / Site / Area / Unit / Assembly /
Device, ISA-88-derived) and a `lifecycle` FSM
(Commissioned -> Active -> Maintenance -> Decommissioned).

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

`AssetName` is the **seventh** trimmed-bounded-name VO. Phase 5a's
gate-review decided to defer `BoundedName` factory extraction at
the 6-instance mark; the trigger was "first per-VO divergence OR
~10 instances". This commit doesn't change that — AssetName stays
byte-identical with the prior 6.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

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


class InvalidAssetNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Asset name must be 1-{ASSET_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


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


@dataclass(frozen=True)
class AssetName:
    """Display name for an asset. Trimmed; 1-200 chars.

    Seventh occurrence of the trimmed-bounded-name VO pattern.
    BoundedName factory extraction stays deferred per the Phase 5a
    gate-review decision (revisit at first per-VO divergence or
    ~10 instances).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > ASSET_NAME_MAX_LENGTH:
            raise InvalidAssetNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Asset:
    """Aggregate root: a physical equipment instance.

    `parent_id` is the immediate parent in the hierarchy tree.
    `None` only when `level == Enterprise` (root). Mutable across
    `AssetRelocated` events (5d).

    Additive facets (5f+): `condition`, `settings`, `ports`,
    `owner`, `persistent_id`. The state-level fields will land
    with defaults so prior events fold cleanly without an upcaster
    (the additive-state pattern documented in CONTRIBUTING.md).
    """

    id: UUID
    name: AssetName
    level: AssetLevel
    parent_id: UUID | None
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED
