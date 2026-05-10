"""The `StoreSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (the subject being
archived on-site). The principal-id of the invoker is supplied
separately by the application handler at call time. Mirrors
`ReturnSubject`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StoreSubject:
    """Archive an existing (Removed) subject on-site."""

    subject_id: UUID
