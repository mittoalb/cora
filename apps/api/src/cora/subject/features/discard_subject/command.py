"""The `DiscardSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (the subject being
destroyed / discarded). The principal-id of the invoker is supplied
separately by the application handler at call time.

`reason` is a free-form operator-supplied string (1-500 chars after
trimming). Required: every irrecoverable Subject disposition must
carry the operator's stated reason for GDPR + sample-handling audit.
Mirrors `DiscardDataset` / `RunStopped` / `RunAborted` /
`RunTruncated` reason fields.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DiscardSubject:
    """Destroy / discard an existing (Removed) subject."""

    subject_id: UUID
    reason: str
