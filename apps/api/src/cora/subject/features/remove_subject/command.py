"""The `RemoveSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (the subject being
removed from the apparatus). The principal-id of the invoker is
supplied separately by the application handler at call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveSubject:
    """Remove an existing subject from the apparatus."""

    subject_id: UUID
