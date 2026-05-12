"""The `DiscardDataset` command, intent dataclass for this slice.

Single-source terminal: `Registered -> Discarded`. Carries the
target dataset's id plus an operator-supplied free-form `reason`
string (1-500 chars after trim; validated at the API boundary AND
defensively at the decider via `DatasetDiscardReason` VO).

GDPR-shaped: the bytes at the URI have been (or are about to be)
deleted from storage; this event keeps the metadata + reason for
audit. The Data BC does NOT issue the storage deletion itself,
that's an out-of-band operator workflow against S3 / Globus /
POSIX. The DatasetDiscarded event records the intent + reason.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DiscardDataset:
    """Discard an existing Dataset (Registered → Discarded)."""

    dataset_id: UUID
    reason: str
