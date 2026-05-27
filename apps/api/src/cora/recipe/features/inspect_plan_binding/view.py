"""Read-side view types for the `inspect_plan_binding` slice.

These are the shapes the handler returns. The route + MCP tool
adapt them to wire-friendly Pydantic models with primitive types.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.equipment.aggregates.asset import AssetCondition, AssetLifecycle
from cora.equipment.aggregates.family import Affordance


class BindingStatus(StrEnum):
    """At-a-glance verdict for a candidate Plan binding.

    Computed from the loaded state. `NO_CAPABILITY` means the bound
    Method has no `capability_id` (legacy shape); the affordance
    guard is skipped per the `define_plan` decider's existing
    behaviour. When BOTH families and affordances are missing,
    status reports `MISSING_FAMILIES` (the primitive check that
    runs first in the decider); both detailed sets remain visible
    in the view so the operator sees the whole picture.
    """

    SATISFIED = "Satisfied"
    MISSING_FAMILIES = "MissingFamilies"
    MISSING_AFFORDANCES = "MissingAffordances"
    NO_CAPABILITY = "NoCapability"


@dataclass(frozen=True)
class WiredAssetBinding:
    """Per-wired-Asset contribution to the binding diagnostic.

    `condition` and `lifecycle` are the Asset's current health +
    lifecycle state at preview time. `family_ids` is the Asset's
    bound Family set. `contributed_affordances` is the union of
    affordances declared by those Families.
    """

    asset_id: UUID
    asset_name: str
    condition: AssetCondition
    lifecycle: AssetLifecycle
    family_ids: frozenset[UUID]
    contributed_affordances: frozenset[Affordance]


@dataclass(frozen=True)
class InspectPlanBindingView:
    """Full binding diagnostic returned by the handler.

    Always populates both `missing_families` and `missing_affordances`
    so the operator sees the whole picture in one read, even when
    the decider would short-circuit on the family check. Empty
    frozensets mean that dimension is satisfied.

    `capability_id` is None when the Method has no Capability
    template (legacy shape); `capability_required_affordances` is
    empty in that case, and `binding_status` reports
    `NO_CAPABILITY`.

    `wired_assets` is sorted by asset_id string form for
    deterministic ordering across replays.

    Forward-compat note: the next phase (when the asset-affordance
    projections land) will surface "other Assets in the facility
    that afford each missing requirement." That payload MUST ship
    as a sibling field (e.g. `missing_affordance_candidates:
    tuple[(Affordance, tuple[CandidateAsset, ...]), ...]`) rather
    than mutate `missing_affordances` into a richer structure --
    keeping this field's shape stable preserves backward
    compatibility for any client that hashes or pattern-matches on
    it today.
    """

    practice_id: UUID
    method_id: UUID
    capability_id: UUID | None
    method_needed_families: frozenset[UUID]
    capability_required_affordances: frozenset[Affordance]
    wired_assets: tuple[WiredAssetBinding, ...]
    missing_families: frozenset[UUID]
    missing_affordances: frozenset[Affordance]
    binding_status: BindingStatus
