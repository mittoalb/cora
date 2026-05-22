"""The `DismountSubject` command — intent dataclass for this slice.

`subject_id` is the target Subject aggregate. `reason` is operator-
supplied free text (1-500 chars) captured on the
`SubjectDismounted` event for audit. The principal-id of the
invoker is supplied separately by the application handler.

The `from_asset_id` is NOT in the command — the decider reads it
from prior state (`Subject.mounted_on_asset_id`), which is
guaranteed non-None when status is in {Mounted, Measured} per the
4b invariant.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DismountSubject:
    """Dismount an existing Subject from its current sample-environment Asset."""

    subject_id: UUID
    reason: str
