"""Mount's update-handler factory (thin wrapper).

Closes over Mount-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

Mirrors `cora.equipment._asset_update_handler.make_asset_update_handler`
and `cora.equipment._frame_update_handler.make_frame_update_handler`;
the per-aggregate scoping rationale (one factory per aggregate, not
one per BC) is documented at the Asset wrapper.

## Mount-side knobs closed over

  - `stream_type = "Mount"`.
  - `target_id_attr = "mount_id"` - every targeted Mount transition
    command exposes `mount_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Equipment BC.
  - The four codec functions imported from
    `cora.equipment.aggregates.mount`.

## Used by

  - `update_placement` (single-stream update; idempotent on equal
    placement at the decider).
  - `uninstall_asset` (single-stream update; state-based precondition
    only, no projection lookup).

## NOT used by

  - `register_mount` (create-style; uses the longhand
    `register_<aggregate>` pattern with idempotency wrap).
  - `decommission_mount` (longhand; loads the `mount_children`
    projection precondition before the pure decider).
  - `install_asset` (longhand; loads the `asset_lookup` projection
    precondition before the pure decider).
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.equipment.aggregates.mount import (
    MountEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler


def make_mount_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[MountEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one single-stream Mount slice."""
    return make_update_handler(
        deps,
        stream_type="Mount",
        target_id_attr="mount_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        extra_log_fields=extra_log_fields,
    )


__all__ = ["make_mount_update_handler"]
