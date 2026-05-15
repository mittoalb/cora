"""The `ActivateClearance` command -- intent dataclass for this slice.

`clearance_id` is the target. No body fields: activating is the
operator's gesture moving an Approved clearance to Active. Separate
from Approved to model APS ESAF "approved but not yet effective" +
DESY DOOR "approved but awaiting beamtime start" semantics.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActivateClearance:
    """Activate an Approved clearance (`Approved -> Active`)."""

    clearance_id: UUID
