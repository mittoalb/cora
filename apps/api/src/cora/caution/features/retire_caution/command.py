"""The `RetireCaution` command -- intent dataclass for this slice.

Retires an Active caution with a closed-reason enum
(`CautionRetireReason`: Resolved / NoLongerApplies / WrongTarget).
Terminal-good: retired cautions cannot be revived; a new caution is
the path forward.

The retiring actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
Mirror of `ExpireClearance` shape.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.caution.aggregates.caution import CautionRetireReason


@dataclass(frozen=True)
class RetireCaution:
    """Retire an Active caution (`Active -> Retired`)."""

    caution_id: UUID
    reason: CautionRetireReason
