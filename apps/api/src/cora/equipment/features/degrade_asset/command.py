"""The `DegradeAsset` command — intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit. The
principal-id of the invoker is supplied separately by the
application handler at call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DegradeAsset:
    """Mark an existing asset as Degraded (works with reduced specs).

    Target-state semantics: moves condition to Degraded from ANY
    source (Nominal / Faulted, or no-op when already Degraded).
    Lifecycle is independent and unaffected.
    """

    asset_id: UUID
    reason: str
