"""The `ReturnSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (the subject being
returned to its owner / submitter). The principal-id of the invoker
is supplied separately by the application handler at call time.
Mirrors `MeasureSubject` / `RemoveSubject`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReturnSubject:
    """Return an existing (Removed) subject to its owner / submitter."""

    subject_id: UUID
