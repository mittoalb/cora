"""The `RegisterClearance` command -- intent dataclass for this slice.

Carries the caller-controlled fields: the clearance's `kind` (12-value
StrEnum covering 9 surveyed facility forms), `title`, `bindings`
(frozenset of typed CORA-aggregate refs + ExternalRefBinding fallback),
`declarations` (frozenset of HazardDeclaration with target +
classifications + mitigations + notes), `risk_band` (optional;
populated for ESRF / MAX IV / DLS / DESY / SLAC variants where green/
yellow/red triage is used; None for APS-style ESAF), and lazy-mint
`external_id`. Optional validity-window fields (`valid_from`,
`valid_until`) capture facility-supplied effective dates.

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports; matches the cross-BC create-style command shape
locked in Access / Trust / Subject / Equipment / Supply / Operation.

Per [[project_safety_clearance_design]]:
  - `kind`: ClearanceKind StrEnum, day-one lock; Pydantic at boundary
    enforces enum membership (-> 422).
  - `title`: bare str, validated 1-200 chars via ClearanceTitle VO at
    decider; Pydantic at boundary also enforces (-> 422 / 400 split).
  - `bindings`: frozenset; non-empty enforced at decider (-> 400).
  - `declarations`: frozenset; empty allowed.
  - `risk_band`: RiskBand | None; APS ESAF leaves None.
  - `external_id`: str | None; lazy-mint.
"""

from dataclasses import dataclass, field
from datetime import datetime

from cora.safety.aggregates.clearance import (
    ClearanceBinding,
    ClearanceKind,
    HazardDeclaration,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand


@dataclass(frozen=True)
class RegisterClearance:
    """Register a new safety-form clearance (lands in `Defined`).

    `facility_code` is the cross-deployment convergent slug of the
    Federation Facility that issued (or will issue) this clearance. The
    handler resolves the slug via `FacilityLookup.lookup_by_code` and the
    decider rejects unknown codes with `ClearanceFacilityNotFoundError`
    (HTTP 404), mirroring the Slice 8A `register_asset` precedent.
    """

    kind: ClearanceKind
    facility_code: str
    title: str
    bindings: frozenset[ClearanceBinding]
    declarations: frozenset[HazardDeclaration] = field(default_factory=frozenset[HazardDeclaration])
    risk_band: RiskBand | None = None
    external_id: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
