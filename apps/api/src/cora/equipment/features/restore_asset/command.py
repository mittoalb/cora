"""The `RestoreAsset` command — intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit.

Naming distinct from `ExitAssetMaintenance`: that command moves
lifecycle (Maintenance -> Active); this one moves condition (any
-> Nominal).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RestoreAsset:
    """Mark an existing asset as Nominal (fully working).

    Target-state semantics: moves condition to Nominal from ANY
    source (Degraded / Faulted, or no-op when already Nominal).
    Lifecycle is independent and unaffected.

    For partial repairs (Faulted -> Degraded), use `degrade_asset`,
    NOT `restore_asset` with a target argument — each slice has a
    fixed target. Operator vocabulary: "I'm restoring it" means
    "back to fully working".
    """

    asset_id: UUID
    reason: str
