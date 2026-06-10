"""The `WithdrawEdition` command for the withdraw_edition slice.

Carries the Edition id plus a mandatory free-form withdrawal reason.
Tombstoning a public DOI MUST carry WHY forever (audit-trail
requirement); the reason is validated by the `WithdrawalReason` VO at
the decider.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class WithdrawEdition:
    """Withdraw a Published Edition: tombstone the DOI, emit Withdrawn."""

    edition_id: UUID
    withdrawal_reason: str
