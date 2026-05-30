"""Context snapshot loaded by the register_mount handler.

The register_mount slice uses single-stream-write + projection-
precondition (Visit BC `take_control_of_surface` precedent;
mirrors decommission_frame's pattern from the prior commit). The
handler loads the `mount_lookup` projection before calling the
decider; the context VO carries the existing mount_id (if any)
that already holds the requested slot_code.

`existing_mount_id` is None when the slot_code is free (allowed to
register). When non-None, the decider raises MountAlreadyExistsError
without I/O.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RegisterMountContext:
    """Snapshot of slot_code uniqueness from mount_lookup projection."""

    existing_mount_id: UUID | None
