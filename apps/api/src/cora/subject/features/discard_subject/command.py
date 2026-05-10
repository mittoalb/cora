"""The `DiscardSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (the subject being
destroyed / discarded). The principal-id of the invoker is supplied
separately by the application handler at call time. Mirrors
`ReturnSubject` / `StoreSubject`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DiscardSubject:
    """Destroy / discard an existing (Removed) subject."""

    subject_id: UUID
