"""Vertical slices for the Caution BC.

Slices:
  - `register_caution`   (genesis -> Active; create-style; idempotency-wrapped)
  - `supersede_caution`  (cross-aggregate; create-style; idempotency-wrapped;
                          two-stream atomic via EventStore.append_streams)
  - `retire_caution`     (Active -> Retired; terminal-good)
  - `get_caution`        (read)

A projection + `list_cautions` slice covers the read side; the
Run.start non-blocking integration is wired through the
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
