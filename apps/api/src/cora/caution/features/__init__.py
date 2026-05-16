"""Vertical slices for the Caution BC.

Phase 11b-a ships:
  - `register_caution`   (genesis -> Active; create-style; idempotency-wrapped)
  - `supersede_caution`  (cross-aggregate; create-style; idempotency-wrapped;
                          two-stream atomic via EventStore.append_streams)
  - `retire_caution`     (Active -> Retired; terminal-good)
  - `get_caution`        (read)

Phase 11b-b adds the projection + `list_cautions` slice.
Phase 11b-c adds the Run.start non-blocking integration via a new
`CautionLookup` port.
"""

from cora.caution.features import (
    get_caution,
    list_cautions,
    register_caution,
    retire_caution,
    supersede_caution,
)

__all__ = [
    "get_caution",
    "list_cautions",
    "register_caution",
    "retire_caution",
    "supersede_caution",
]
