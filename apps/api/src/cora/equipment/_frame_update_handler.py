"""Frame's update-handler factory (thin wrapper).

Closes over Frame-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

Mirrors `cora.equipment._asset_update_handler.make_asset_update_handler`;
the per-aggregate scoping rationale (one factory per aggregate, not
one per BC) is documented there.

## Frame-side knobs closed over

  - `stream_type = "Frame"`.
  - `target_id_attr = "frame_id"` - every targeted Frame transition
    command exposes `frame_id: UUID` (UpdateFrame at v1; future
    reparent_frame if it ever lands).
  - `unauthorized_error = UnauthorizedError` from the Equipment BC.
  - The four codec functions imported from
    `cora.equipment.aggregates.frame`.

## Why not used by `decommission_frame`

`decommission_frame` loads a cross-aggregate projection
(`frame_consumers`) before deciding, so its handler is longhand and
does not use this factory. The factory is for single-stream updates
only (matches `update_handler.make_update_handler`'s contract).
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.equipment.aggregates.frame import (
    FrameEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler


def make_frame_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[FrameEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one single-stream Frame slice."""
    return make_update_handler(
        deps,
        stream_type="Frame",
        target_id_attr="frame_id",
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


__all__ = ["make_frame_update_handler"]
