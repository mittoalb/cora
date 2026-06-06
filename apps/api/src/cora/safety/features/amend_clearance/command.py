"""The `AmendClearance` command -- intent dataclass for this slice.

Amends an Active parent clearance by creating a new child clearance
with the supplied fields, atomically with the parent's transition to
`Superseded`. The child gets `parent_id=<parent>` on its
genesis event; the parent gets `ClearanceSuperseded(by_clearance_id=
<child>)` on its stream.

The child's fields are operator-supplied (NOT copied from parent) so
amendments can revise any aspect: title, bindings, declarations, risk
band, validity window. The parent-child link establishes the
amendment chain; field-level continuity is the operator's call.

The amending actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from cora.safety.aggregates.clearance import (
    ClearanceBinding,
    ClearanceKind,
    HazardDeclaration,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand


@dataclass(frozen=True)
class AmendClearance:
    """Amend an Active clearance with a new child (`parent: Active -> Superseded`).

    Fields mirror `RegisterClearance` (the child IS a registration) +
    `parent_id`. The child clearance lands in `Defined` per
    the standard genesis-event convention; the operator subsequently
    drives it through the FSM (submit / start_review / etc.) as a
    normal clearance.
    """

    parent_id: UUID
    kind: ClearanceKind
    facility_asset_id: UUID
    title: str
    bindings: frozenset[ClearanceBinding]
    declarations: frozenset[HazardDeclaration] = field(default_factory=frozenset[HazardDeclaration])
    risk_band: RiskBand | None = None
    external_id: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
