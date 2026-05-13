"""The `FaultAsset` command — intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FaultAsset:
    """Mark an existing asset as Faulted (does not work, requires repair).

    Target-state semantics: moves condition to Faulted from ANY
    source (Nominal / Degraded, or no-op when already Faulted).
    Lifecycle is independent and unaffected.
    """

    asset_id: UUID
    reason: str
