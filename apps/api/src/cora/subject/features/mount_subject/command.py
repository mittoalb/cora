"""The `MountSubject` command — intent dataclass for this slice.

`subject_id` is the **target** Subject aggregate (caller-supplied:
the subject to mount). The principal-id of the invoker is supplied
separately by the application handler at call time, not in the
command. Mirrors `DeactivateActor` — same update-style command shape.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MountSubject:
    """Mount an existing subject on the apparatus."""

    subject_id: UUID
