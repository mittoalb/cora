"""Asset's update-handler factory (thin wrapper).

Closes over Asset-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

Cross-BC hoist landed once Recipe and Run shipped a combined 11
byte-identical longhand handlers.

## Per-aggregate, not per-BC

Equipment owns two aggregates (Family + Asset). This factory
only handles Asset transitions; if Family lifecycle
transitions land they get their own
`make_capability_update_handler` factory in a sibling module
rather than parameterizing this one (per-aggregate scoping keeps
each factory honest about what it knows). Subject's
`make_subject_update_handler` looks BC-named only because Subject
is a single-aggregate BC; the same per-aggregate scoping applies.

## Asset-side knobs closed over

  - `stream_type = "Asset"`.
  - `target_id_attr = "asset_id"` — every targeted Asset
    transition command exposes `asset_id: UUID` (Activate /
    Decommission / Relocate / EnterAssetMaintenance /
    ExitAssetMaintenance / DegradeAsset / FaultAsset /
    RestoreAsset). RelocateAsset also carries `to_parent_id`,
    which it logs by passing `extra_log_fields` (preserving the
    pre-hoist log shape).
  - `unauthorized_error = UnauthorizedError` from the Equipment BC.
  - The four codec functions imported from
    `cora.equipment.aggregates.asset`.

The condition slices (5g-b: degrade / fault / restore) carry
`reason: str` alongside `asset_id`. That field IS captured on the
emitted event payload but is intentionally NOT logged at the
handler boundary; it is therefore not surfaced via
`extra_log_fields` either.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.equipment.aggregates.asset import (
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler


def make_asset_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AssetEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Asset slice."""
    return make_update_handler(
        deps,
        stream_type="Asset",
        target_id_attr="asset_id",
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


__all__ = ["make_asset_update_handler"]
