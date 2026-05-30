"""Pure decider for the `RegisterMount` command.

Pure function: given the current Mount state (None for a fresh
stream), the loaded context (slot_code uniqueness), and the command,
returns the events to append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

## Invariants

  - State must be None (genesis-only) -> MountAlreadyExistsError
    via stream collision (essentially impossible with UUIDv7 ids;
    defensive guard).
  - `context.existing_mount_id` must be None (slot_code free)
    -> MountAlreadyExistsError when collision; carries the
    pre-existing mount_id for diagnostics.
  - slot_code must be valid -> InvalidSlotCodeError (via SlotCode VO).

Eventual-consistency: parent_mount_id existence NOT verified;
placement.parent_frame existence NOT verified.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.mount import (
    Mount,
    MountAlreadyExistsError,
    MountRegistered,
    SlotCode,
)
from cora.equipment.features.register_mount.command import RegisterMount
from cora.equipment.features.register_mount.context import RegisterMountContext


def decide(
    state: Mount | None,
    command: RegisterMount,
    *,
    context: RegisterMountContext,
    now: datetime,
    new_id: UUID,
) -> list[MountRegistered]:
    """Decide the events produced by registering a new mount.

    Invariants:
      - State must be None (genesis-only) -> MountAlreadyExistsError.
      - context.existing_mount_id must be None (slot_code free)
        -> MountAlreadyExistsError carrying the pre-existing mount_id.
      - slot_code must be valid -> InvalidSlotCodeError (via SlotCode VO).
    """
    if state is not None:
        raise MountAlreadyExistsError(state.id)
    if context.existing_mount_id is not None:
        # Slot code is already in use by another Active mount; the
        # collision is between distinct mount_ids sharing the same
        # external alias. Surface the pre-existing mount_id so the
        # operator can target it or decommission it first.
        raise MountAlreadyExistsError(context.existing_mount_id)

    # Validate slot_code via the SlotCode VO (raises InvalidSlotCodeError
    # if empty / whitespace-only / overlong).
    slot_code = SlotCode(command.slot_code)

    return [
        MountRegistered(
            mount_id=new_id,
            slot_code=slot_code.value,
            parent_mount_id=command.parent_mount_id,
            placement=command.placement,
            drawing=command.drawing,
            occurred_at=now,
        )
    ]
