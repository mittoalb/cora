"""The `MeasureSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (the subject being
measured). The principal-id of the invoker is supplied separately by
the application handler at call time. Mirrors `MountSubject`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MeasureSubject:
    """Record that a measurement was taken on an existing subject."""

    subject_id: UUID
