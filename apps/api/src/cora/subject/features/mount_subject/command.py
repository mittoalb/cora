"""The `MountSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (caller-supplied:
the subject to mount). `asset_id` is the sample-environment
`Equipment.Asset` the subject is being mounted on. Both ids are
caller-supplied; the principal-id of the invoker is supplied
separately by the application handler at call time, not in the
command.

`reason` (4f) is operator-supplied free text (1-500 chars) captured
on the `SubjectMounted` event for audit. Required; matches
`relocate_asset.reason` / 5g-b condition-event precedent.

The handler pre-loads the target Asset and bundles it into a
`MountSubjectContext`; the pure decider validates the Asset's
lifecycle (Active only) and emits `SubjectMounted(asset_id=..., reason=...)`.
Cross-aggregate validation pattern per CONTRIBUTING.md.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MountSubject:
    """Mount an existing subject onto a sample-environment Asset."""

    subject_id: UUID
    asset_id: UUID
    reason: str
