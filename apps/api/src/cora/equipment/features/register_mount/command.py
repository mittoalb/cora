"""The `RegisterMount` command - intent dataclass for the register_mount slice.

Carries the caller-controlled fields: slot_code (external alias),
optional parent_mount_id (None for top-level slots), required
placement (every slot has a position), optional drawing (engineering
reference for the slot itself).

Server-side concerns (new mount_id, wall-clock timestamp, correlation
id, per-event ids) are injected by the handler from infrastructure
ports. installed_asset_id is implicit (None at registration; the
install_asset slice transitions a vacant slot to occupied).

Eventual-consistency stance:
- parent_mount_id existence is NOT verified at write time (matches
  Asset.parent_id, Frame.parent_frame_id precedent).
- placement.parent_frame_id existence is NOT verified at write time
  (mirrors the same precedent for cross-aggregate references).
- slot_code uniqueness IS enforced at the handler layer via the
  mount_slot_code projection precondition before reaching the decider.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates._placement import Placement


@dataclass(frozen=True)
class RegisterMount:
    """Register a new mount with the given slot code, parent, placement, and drawing."""

    slot_code: str
    parent_mount_id: UUID | None
    placement: Placement
    drawing: Drawing | None
