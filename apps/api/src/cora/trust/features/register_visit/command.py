"""The `RegisterVisit` command -- intent dataclass for this slice.

Genesis command. Caller-supplied `visit_id` so a BSS subscriber can
mint deterministic UUIDs in Phase iota (`uuid5(NAMESPACE_BSS,
f'{scheme}:{external_id}')`) for replay-safe ingest, while operator-
direct registration can also supply a UUID.

`part_of_visit_id` and `external_refs` are on the command from Phase
beta (closes P2-Design-3 migration drift) even though their API surface
lands Phase delta + Phase epsilon respectively.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from cora.infrastructure.external_ref import ExternalRef
from cora.trust.aggregates.visit import VisitType


@dataclass(frozen=True)
class RegisterVisit:
    """Register a new Visit on a Surface under a Policy.

    `policy_id`: REQUIRED -- the authz envelope. Visit references the
    same Policy that Trust's Authorize port gates commands against, so
    a single source of truth answers "is this actor allowed to act in
    this Visit's context".

    `surface_id`: REQUIRED -- Visit is Surface-scoped (not Policy-
    scoped). One Policy may host many Visits across Surfaces (S8
    multi-instrument case).

    `type`: REQUIRED closed enum classifying the operational nature.
    Replaces sentinel-value anti-pattern (no `gup=0` magic).

    `planned_start_at` + `planned_end_at`: REQUIRED. Decider enforces
    `planned_end_at > planned_start_at`.

    `part_of_visit_id`: OPTIONAL self-FK for nested commissioning
    (Phase delta API surface; field already on event payload).

    `external_refs`: OPTIONAL anti-corruption refs to upstream-
    deferred concepts (Phase epsilon API surface; field already on
    event payload).
    """

    visit_id: UUID
    policy_id: UUID
    surface_id: UUID
    type: VisitType
    planned_start_at: datetime
    planned_end_at: datetime
    part_of_visit_id: UUID | None = None
    external_refs: frozenset[ExternalRef] = field(default_factory=frozenset[ExternalRef])
